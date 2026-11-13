"""LLM-as-a-judge: Gemini (Vertex AI) checks that a CRM record is faithful to the notes.

Le prompt est celui de `docs/langfuse_judge_prompt.md`. On appelle Gemini par
Vertex AI avec les identifiants ADC du projet GCP : pas de clé API à gérer (la
connexion Google AI Studio de Langfuse échoue, modèles saturés en offre gratuite).
Le score `fidelite_fiche` (1, 0.5 ou 0) et la justification sont ensuite envoyés
dans Langfuse, sur la trace de la fiche.
"""

import json
import re
from functools import cache

from google import genai
from google.genai import types

from src.constants import PROJECT_ID, PROJECT_ROOT_PATH

JUDGE_MODEL = "gemini-3.5-flash"
SCORE_NAME = "fidelite_fiche"
PROMPT_PATH = PROJECT_ROOT_PATH / "docs" / "langfuse_judge_prompt.md"
ALLOWED_SCORES = (0.0, 0.5, 1.0)


@cache
def _prompt_template() -> str:
    """The judge prompt (the ```text block of the doc), with {{input}} / {{output}}."""
    text = PROMPT_PATH.read_text(encoding="utf-8")
    return re.search(r"```text\n(.*?)\n```", text, re.DOTALL).group(1)


@cache
def client() -> genai.Client:
    return genai.Client(vertexai=True, project=PROJECT_ID, location="global")


def judge(note: str, record: str) -> tuple[float, str]:
    """Score a record against its note: (score in {0, 0.5, 1}, one-sentence reason)."""
    prompt = (
        _prompt_template().replace("{{input}}", note).replace("{{output}}", record)
        + "\n\nRéponds en JSON, avec le raisonnement rédigé en anglais : "
        + '{"raisonnement": "...", "score": 0 | 0.5 | 1}'
    )
    response = client().models.generate_content(
        model=JUDGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "raisonnement": {"type": "string"},
                    "score": {"type": "number"},
                },
                "required": ["raisonnement", "score"],
            },
        ),
    )
    answer = json.loads(response.text)
    score = min(ALLOWED_SCORES, key=lambda allowed: abs(allowed - answer["score"]))
    return score, answer["raisonnement"].strip()
