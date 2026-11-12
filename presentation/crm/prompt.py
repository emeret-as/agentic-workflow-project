"""Prompt envoyé à Phi-3 : exactement celui de l'entraînement et de l'app Chainlit.

La consigne vient de src/crm_schema.py (build_user_content) : le modèle reçoit
en démo le même texte qu'à l'entraînement. PROMPT_VERSION est envoyé à Langfuse.
"""

import re

from src.crm_schema import build_user_content

PROMPT_VERSION = "crm-fr-v1"


def build_prompt(notes: str) -> str:
    """Applique le format de conversation de Phi-3 (comme src/app/main.py)."""
    return f"<|user|>\n{build_user_content(notes.strip())}<|end|>\n<|assistant|>\n"


def extract_answer(raw_output: str) -> str:
    """Garde uniquement la réponse du modèle (même règle que l'app Chainlit).

    Le handler renvoie « <|user|>…<|end|><|assistant|> réponse<|end|>… » : on prend
    ce qui suit <|assistant|> et on coupe à la première balise de fin.
    """
    match = re.search(
        r"<\|assistant\|>(.*?)(?:<\|end\|>|<\|endoftext\|>|$)", raw_output, re.DOTALL
    )
    return match.group(1).strip() if match else raw_output.strip()
