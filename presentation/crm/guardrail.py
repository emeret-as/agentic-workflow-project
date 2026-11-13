"""Garde-fou : on n'affiche une fiche que si la sortie du modèle est conforme.

Mêmes règles que `is_valid_record` (src/crm_schema.py), qui sert aussi à
l'évaluation du pipeline et aux scores de l'app Chainlit. Ici, chaque règle non
respectée donne un message lisible pour la démo.
- json_valid   : la sortie contient un objet JSON lisible ;
- schema_valid : les 7 clés dans l'ordre, les bons types, les listes fermées.
"""

import re
from dataclasses import dataclass, field

from crm.schema import FIELD_LABELS
from src.crm_schema import FIELDS, NEEDS, NEXT_ACTIONS, is_valid_record, parse_json

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class GuardrailResult:
    json_valid: bool
    schema_valid: bool
    record: dict | None  # la fiche, seulement si schema_valid
    errors: list[str] = field(default_factory=list)


def _schema_errors(record: dict) -> list[str]:
    """Liste, en français, les règles du schéma que la fiche ne respecte pas."""
    errors = []
    missing = [key for key in FIELDS if key not in record]
    extra = [key for key in record if key not in FIELDS]
    if missing:
        errors.append(f"Missing fields: {', '.join(missing)}")
    if extra:
        errors.append(f"Unexpected fields: {', '.join(extra)}")
    if not missing and not extra and list(record) != FIELDS:
        errors.append("Fields are not in the expected order")
    company = record.get("company")
    if not isinstance(company, str) or not company.strip():
        errors.append("Company missing: a record must always have one")
    for key in ("contact_name", "contact_role"):
        value = record.get(key)
        if value is not None and not (isinstance(value, str) and value.strip()):
            errors.append(f"{FIELD_LABELS[key]}: text or null expected")
    budget = record.get("budget_eur")
    if budget is not None and not (
        isinstance(budget, int) and not isinstance(budget, bool) and budget > 0
    ):
        errors.append("Budget: integer amount in euros expected")
    deadline = record.get("deadline")
    if deadline is not None and not (
        isinstance(deadline, str) and _ISO_DATE.match(deadline)
    ):
        errors.append("Deadline: date in YYYY-MM-DD format expected")
    if "need" in record and record["need"] not in NEEDS:
        errors.append(f"Need not in the list: “{record['need']}”")
    if "next_action" in record and record["next_action"] not in NEXT_ACTIONS:
        errors.append(f"Next action not in the list: “{record['next_action']}”")
    return errors


def check_output(answer: str) -> GuardrailResult:
    """Vérifie la réponse du modèle et renvoie la fiche si elle est conforme."""
    record = parse_json(answer)
    if record is None:
        return GuardrailResult(False, False, None, ["No readable JSON in the answer"])
    if is_valid_record(record):
        return GuardrailResult(True, True, record)
    errors = _schema_errors(record) or ["Record does not match the schema"]
    return GuardrailResult(True, False, None, errors)
