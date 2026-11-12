"""Format de la fiche CRM, repris du schéma du projet (src/crm_schema.py).

Le schéma (clés, listes fermées, consigne) est défini une seule fois, dans
src/crm_schema.py : c'est lui qui a servi à générer les données, entraîner et
évaluer le modèle. Ici on ajoute seulement ce qu'il faut pour l'affichage :
libellés en français et mise en forme des valeurs.
"""

from datetime import date

from src.crm_schema import FIELDS as FIELD_KEYS
from src.crm_schema import NEEDS, NEXT_ACTIONS

# (clé JSON, libellé affiché), dans l'ordre du JSON produit par le modèle
FIELDS: list[tuple[str, str]] = list(
    zip(
        FIELD_KEYS,
        [
            "Entreprise",
            "Interlocuteur",
            "Fonction",
            "Besoin",
            "Budget",
            "Prochaine action",
            "Échéance",
        ],
        strict=True,
    )
)
FIELD_LABELS: dict[str, str] = dict(FIELDS)

# Libellés courts des listes fermées (les valeurs du JSON restent en anglais)
NEED_LABELS: dict[str, str] = {
    "crm_migration": "Migration du CRM",
    "data_platform": "Plateforme de données",
    "cybersecurity": "Cybersécurité",
    "cloud_migration": "Migration vers le cloud",
    "ai_assistant": "Assistant IA interne",
    "process_automation": "Automatisation de processus",
    "analytics_dashboard": "Tableaux de bord",
    "team_training": "Formation des équipes",
}
NEXT_ACTION_LABELS: dict[str, str] = {
    "send_proposal": "Envoyer une proposition chiffrée",
    "schedule_demo": "Organiser une démonstration",
    "send_documentation": "Envoyer la documentation",
    "schedule_followup_call": "Planifier un appel de suivi",
    "involve_stakeholder": "Faire venir un décideur",
    "internal_review": "Attendre la validation interne",
}
assert list(NEED_LABELS) == NEEDS and list(NEXT_ACTION_LABELS) == NEXT_ACTIONS

_MONTHS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


def format_value(key: str, value) -> str:
    """Valeur lisible pour l'interface : « 124 000 € », « 26 février 2027 »…"""
    if value is None:
        return ""
    if key == "budget_eur" and isinstance(value, int):
        return f"{value:,} €".replace(",", " ")
    if key == "need":
        return NEED_LABELS.get(value, str(value))
    if key == "next_action":
        return NEXT_ACTION_LABELS.get(value, str(value))
    if key == "deadline":
        try:
            day = date.fromisoformat(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"
    return str(value)
