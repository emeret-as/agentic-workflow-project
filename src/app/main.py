"""Chainlit web app calling the fine-tuned Yoda model deployed on Vertex AI.

Lancement, depuis la racine du repo :
    PYTHONPATH=. uv run --env-file .env chainlit run src/app/main.py
"""

import re
import subprocess
import time
from typing import Any

import chainlit as cl
import requests
from langfuse import Langfuse, observe

from src.constants import ENDPOINT_ID, PROJECT_NUMBER, REGION

# Chainlit émet ses propres traces OpenTelemetry : on les écarte de Langfuse pour
# ne garder que nos spans et generations
langfuse = Langfuse(blocked_instrumentation_scopes=["chainlit"])

ENDPOINT_URL = (
    f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_NUMBER}"
    f"/locations/{REGION}/endpoints/{ENDPOINT_ID}:predict"
)
REQUEST_TIMEOUT_SECONDS = 120

# Paramètres de génération envoyés à l'endpoint. Greedy comme dans le pipeline
# d'évaluation (reproductible) ; 64 tokens suffisent pour une phrase de Yoda.
GENERATION_PARAMETERS: dict[str, Any] = {"max_new_tokens": 64, "do_sample": False}


def build_prompt(sentence: str) -> str:
    """Apply the Phi-3 chat template (same format as during fine-tuning)."""
    return f"<|user|>\n{sentence}<|end|>\n<|assistant|>\n"


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
    """Get an access token for the current gcloud user (dev only)."""
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True
    ).strip()


def call_endpoint(sentence: str) -> str:
    """Send the sentence to the Vertex AI endpoint and return the raw response.

    Logue dans Langfuse une generation : prompt + paramètres en entrée, réponse
    brute en sortie, avec le nom et la version du modèle renvoyés par Vertex AI.
    """
    prompt = build_prompt(sentence)
    model_input = {
        "instances": [{"input": prompt}],
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


@observe(name="User Message")
def answer(message: cl.Message) -> str:
    """Answer a user message with the fine-tuned model (traced in Langfuse)."""
    langfuse.update_current_span(input=message.content)
    raw_output = call_endpoint(message.content)
    extracted = extract_response(raw_output)
    langfuse.update_current_span(output=extracted)
    return extracted


@cl.on_message
async def main(message: cl.Message) -> None:
    """Handle a user message: call the model and send back its answer."""
    try:
        # requests est bloquant : on le sort de la boucle asynchrone de Chainlit
        response = await cl.make_async(answer)(message)
    except (requests.RequestException, subprocess.CalledProcessError) as error:
        response = f"Erreur lors de l'appel à l'endpoint : {error}"
    await cl.Message(content=response).send()
