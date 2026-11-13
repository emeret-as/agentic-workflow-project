"""Chainlit web app: meeting notes -> CRM record, using the model deployed on Vertex AI.

Lancement, depuis la racine du repo :
    PYTHONPATH=. uv run --env-file .env chainlit run src/app/main.py
"""

import json
import re
import time
from typing import Any

import chainlit as cl
import google.auth
import requests
from google.auth.transport.requests import Request
from langfuse import Langfuse, observe

from src.constants import ENDPOINT_ID, PROJECT_NUMBER, REGION
from src.crm_schema import build_user_content, is_valid_record, normalize, parse_json
from src.llm_judge import SCORE_NAME, judge

# Chainlit émet ses propres traces OpenTelemetry : on les écarte de Langfuse pour
# ne garder que nos spans et generations
langfuse = Langfuse(blocked_instrumentation_scopes=["chainlit"])

ENDPOINT_URL = (
    f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_NUMBER}"
    f"/locations/{REGION}/endpoints/{ENDPOINT_ID}:predict"
)
REQUEST_TIMEOUT_SECONDS = 120

# Paramètres de génération envoyés à l'endpoint. Greedy comme dans le pipeline
# d'évaluation (reproductible) ; la fiche JSON fait 60 à 95 tokens.
GENERATION_PARAMETERS: dict[str, Any] = {"max_new_tokens": 160, "do_sample": False}

# Garde-fou d'entrée : le modèle a été entraîné sur des notes d'au plus ~200 mots
# (512 tokens). Au-delà, la qualité n'est plus garantie, on refuse plutôt que
# de renvoyer une fiche douteuse.
MAX_NOTE_CHARS = 3000

_credentials, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def build_prompt(note: str) -> str:
    """Apply the Phi-3 chat template (same format as during fine-tuning)."""
    return f"<|user|>\n{build_user_content(note)}<|end|>\n<|assistant|>\n"


def extract_response(model_output: str) -> str:
    """Extract the assistant answer from the raw model output.

    Le handler renvoie "<|user|>...<|end|>\\n<|assistant|>\\nRéponse<|end|>...".
    """
    match = re.search(
        r"<\|assistant\|>(.*?)(?:<\|end\|>|<\|endoftext\|>|$)",
        model_output,
        re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def get_access_token() -> str:
    """Get a Google access token from the Application Default Credentials."""
    if not _credentials.valid:
        _credentials.refresh(Request())
    return _credentials.token


def call_endpoint(note: str) -> str:
    """Send the note to the Vertex AI endpoint and return the raw response.

    Logue dans Langfuse une generation : prompt + paramètres en entrée, réponse
    brute en sortie, avec le nom et la version du modèle renvoyés par Vertex AI.
    """
    model_input = {
        "instances": [{"input": build_prompt(note)}],
        "parameters": GENERATION_PARAMETERS,
    }
    with langfuse.start_as_current_generation(name="Vertex AI endpoint") as gen:
        started_at = time.perf_counter()
        response = requests.post(
            ENDPOINT_URL,
            headers={
                "Authorization": f"Bearer {get_access_token()}",
                "Content-Type": "application/json",
            },
            json=model_input,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        latency_seconds = time.perf_counter() - started_at
        response.raise_for_status()
        payload = response.json()

        gen.update(
            input=model_input,
            output=payload["predictions"][0],
            model=payload.get("modelDisplayName"),
            version=payload.get("modelVersionId"),
            metadata={
                **GENERATION_PARAMETERS,
                "latency_seconds": latency_seconds,
                "deployed_model_id": payload.get("deployedModelId"),
                "model_resource": payload.get("model"),
            },
        )
    return payload["predictions"][0]


def names_grounded(record: dict[str, Any], note: str) -> bool:
    """Check that the company and contact name given by the model appear in the note.

    Proxy d'hallucination sans référence : un nom absent du texte a été inventé.
    """
    text = normalize(note)
    names = [record.get("company"), record.get("contact_name")]
    return all(name is None or normalize(name) in text for name in names)


def score_output(note: str, extracted: str) -> dict[str, float]:
    """Compute reference-free quality scores for a model output."""
    record = parse_json(extracted)
    valid_schema = is_valid_record(record)
    return {
        "json_valid": float(record is not None),
        "schema_valid": float(valid_schema),
        "names_grounded": float(valid_schema and names_grounded(record, note)),
    }


@observe(name="User Message")
def answer(note: str) -> str:
    """Extract a CRM record from meeting notes (traced and scored in Langfuse)."""
    langfuse.update_current_span(input=note)
    raw_output = call_endpoint(note)
    extracted = extract_response(raw_output)
    langfuse.update_current_span(output=extracted)
    scores = score_output(note, extracted)
    for name, value in scores.items():
        langfuse.score_current_span(name=name, value=value, data_type="NUMERIC")
    if scores["schema_valid"]:
        # Juge LLM (Gemini sur Vertex AI) : la fiche est-elle fidèle à la note ?
        try:
            score, reason = judge(note, extracted)
            langfuse.score_current_span(
                name=SCORE_NAME, value=score, data_type="NUMERIC", comment=reason
            )
        except Exception as error:  # noqa: BLE001  juge indisponible : l'app répond quand même
            langfuse.update_current_span(metadata={"judge_error": str(error)})
    return extracted


def format_answer(extracted: str) -> str:
    """Format the model output for display; warn when it is not a valid record."""
    record = parse_json(extracted)
    if not is_valid_record(record):
        return (
            "⚠️ La fiche générée n'est pas valide, à ne pas utiliser. "
            f"Sortie brute du modèle :\n\n```\n{extracted}\n```"
        )
    return "```json\n" + json.dumps(record, ensure_ascii=False, indent=2) + "\n```"


@cl.on_message
async def main(message: cl.Message) -> None:
    """Handle a user message: call the model and send back the CRM record."""
    if len(message.content) > MAX_NOTE_CHARS:
        await cl.Message(
            content=f"Note trop longue ({len(message.content)} caractères, "
            f"maximum {MAX_NOTE_CHARS}). Résume-la ou découpe-la."
        ).send()
        return
    try:
        # requests est bloquant : on le sort de la boucle asynchrone de Chainlit
        extracted = await cl.make_async(answer)(message.content)
        response = format_answer(extracted)
    except (requests.RequestException, google.auth.exceptions.GoogleAuthError) as error:
        response = f"Erreur lors de l'appel à l'endpoint : {error}"
    await cl.Message(content=response).send()
