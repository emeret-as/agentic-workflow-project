"""CRM record schema shared by the dataset generator, the handler tests and the app.

Cas d'usage : transformer des notes de réunion commerciale (texte libre, en
français) en une fiche CRM JSON à 7 champs.

Les composants Kubeflow (`src/pipeline_components/`) sont autonomes et ne
peuvent pas importer ce module : ils en dupliquent les parties utiles. Garder
les deux versions alignées (vérifié par `local_tests/crm_metrics_test.py`).
"""

import json
import re
import unicodedata
from typing import Any

# Ordre fixe des clés : c'est aussi l'ordre du JSON que le modèle doit produire
FIELDS = [
    "company",
    "contact_name",
    "contact_role",
    "need",
    "budget_eur",
    "next_action",
    "deadline",
]
# Champs qui valent null quand l'information est absente des notes
NULLABLE_FIELDS = ["contact_name", "contact_role", "budget_eur", "deadline"]

# Listes fermées (comme les listes de choix d'un vrai CRM) : clé -> description
NEED_DESCRIPTIONS = {
    "crm_migration": "migrer ou moderniser leur CRM / outil de gestion commerciale",
    "data_platform": "mettre en place une plateforme de données centralisée",
    "cybersecurity": "renforcer leur cybersécurité",
    "cloud_migration": "migrer des applications vers le cloud",
    "ai_assistant": "déployer un assistant IA ou un chatbot interne",
    "process_automation": "automatiser des processus métier",
    "analytics_dashboard": "obtenir des tableaux de bord de pilotage",
    "team_training": "former leurs équipes",
}
NEXT_ACTION_DESCRIPTIONS = {
    "send_proposal": "envoyer une proposition commerciale chiffrée",
    "schedule_demo": "organiser une démonstration",
    "send_documentation": "envoyer de la documentation et des références clients",
    "schedule_followup_call": "planifier un nouvel appel de suivi",
    "involve_stakeholder": "faire participer un décideur à un prochain échange",
    "internal_review": "attendre la validation interne du client avant toute suite",
}
NEEDS = list(NEED_DESCRIPTIONS)
NEXT_ACTIONS = list(NEXT_ACTION_DESCRIPTIONS)

# Consigne placée devant les notes dans le message utilisateur (entraînement,
# inférence, handler et app doivent utiliser exactement le même texte)
INSTRUCTION = (
    "Extrais la fiche CRM au format JSON à partir des notes de réunion ci-dessous. "
    "Clés : company, contact_name, contact_role, need, budget_eur, next_action, "
    "deadline. Utilise null quand l'information est absente.\n\n"
)

_DEADLINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def build_user_content(note: str) -> str:
    """Build the user message: instruction followed by the raw meeting notes."""
    return INSTRUCTION + note


def to_json(record: dict[str, Any]) -> str:
    """Serialize a record with fixed key order, compact and without ASCII escapes."""
    return json.dumps(
        {field: record.get(field) for field in FIELDS}, ensure_ascii=False
    )


def parse_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object found in a model output, or None if invalid."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_valid_record(record: dict[str, Any] | None) -> bool:
    """Check keys, types and closed lists of a record."""
    if record is None or list(record) != FIELDS:
        return False
    company = record["company"]
    if not isinstance(company, str) or not company.strip():
        return False
    for field in ("contact_name", "contact_role"):
        value = record[field]
        if value is not None and not (isinstance(value, str) and value.strip()):
            return False
    budget = record["budget_eur"]
    if budget is not None and not (
        isinstance(budget, int) and not isinstance(budget, bool) and budget > 0
    ):
        return False
    deadline = record["deadline"]
    if deadline is not None and not (
        isinstance(deadline, str) and _DEADLINE_RE.match(deadline)
    ):
        return False
    return record["need"] in NEEDS and record["next_action"] in NEXT_ACTIONS


def has_corrupted_text(text: str) -> bool:
    """Detect control, invisible or replacement characters (corrupted LLM output)."""
    return any(
        unicodedata.category(char)[0] == "C" and char not in "\n\t" or char == "\ufffd"
        for char in text
    )


def normalize(value: Any) -> Any:
    """Normalize a field value for comparison (case, accents, spaces)."""
    if isinstance(value, str):
        decomposed = unicodedata.normalize("NFKD", value)
        stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
        return " ".join(stripped.split()).casefold()
    return value
