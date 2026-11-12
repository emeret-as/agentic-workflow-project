"""Retours de l'utilisateur envoyés dans Langfuse, rattachés à la trace de l'extraction.

La fiche validée (éventuellement corrigée) par le commercial est la « bonne
réponse » : c'est ainsi que le produit récolte de la vérité terrain (session 5).
"""

import json

from crm import config
from src.crm_schema import FIELDS as FIELD_KEYS


def send_thumbs(trace_id: str, thumbs_up: bool) -> None:
    if not (config.LANGFUSE_ENABLED and trace_id):
        return
    from langfuse import get_client

    langfuse = get_client()
    langfuse.create_score(
        name="avis_utilisateur",
        value=1.0 if thumbs_up else 0.0,
        trace_id=trace_id,
        data_type="BOOLEAN",
        comment="pouce levé" if thumbs_up else "pouce baissé",
    )
    langfuse.flush()


def count_changes(original: dict | None, corrected: dict) -> int:
    original = original or {}
    return sum(original.get(key) != corrected.get(key) for key in FIELD_KEYS)


def send_validation(trace_id: str, original: dict | None, corrected: dict) -> int:
    """Envoie la fiche validée et le nombre de champs corrigés. Renvoie ce nombre."""
    n_changed = count_changes(original, corrected)
    if config.LANGFUSE_ENABLED and trace_id:
        from langfuse import get_client

        langfuse = get_client()
        langfuse.create_score(
            name="champs_corriges",
            value=float(n_changed),
            trace_id=trace_id,
            data_type="NUMERIC",
            comment=json.dumps(corrected, ensure_ascii=False),
        )
        langfuse.flush()
    return n_changed
