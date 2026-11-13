"""Tests de la logique de l'app de présentation (sans Streamlit, sans GCP).

Lancer depuis la racine du repo :
    uv run python -m pytest presentation/tests -q
"""

import json
import sys
from pathlib import Path

PRESENTATION = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PRESENTATION), str(PRESENTATION.parent)]

from crm.extraction import names_grounded
from crm.field_check import (
    CHECK,
    FOUND,
    MISSING,
    NOT_CHECKED,
    field_status,
    find_date,
    parse_amounts,
)
from crm.guardrail import check_output
from crm.prompt import build_prompt, extract_answer
from crm.schema import format_value
from ui.components import highlighted_notes_html, record_card_html

from src.crm_schema import INSTRUCTION, to_json

NOTES = (
    "Appel avec Camille Roux, Directeur informatique chez Clinique Duchêne. "
    "Ils veulent migrer leur CRM, budget 124 k€, échéance le 26/02/2027. "
    "Leur séminaire a lieu le 12 mars. Prochaine étape : inviter leur sponsor."
)
RECORD = {
    "company": "Clinique Duchêne",
    "contact_name": "Camille Roux",
    "contact_role": "Directeur informatique",
    "need": "crm_migration",
    "budget_eur": 124000,
    "next_action": "involve_stakeholder",
    "deadline": "2027-02-26",
}


def test_prompt_matches_training_format_and_round_trips():
    prompt = build_prompt(NOTES)
    assert prompt == f"<|user|>\n{INSTRUCTION}{NOTES}<|end|>\n<|assistant|>\n"
    raw = (
        prompt.replace("\n<|assistant|>\n", "<|assistant|> ")
        + to_json(RECORD)
        + "<|end|><|endoftext|>"
    )
    assert json.loads(extract_answer(raw)) == RECORD


def test_guardrail_accepts_valid_record():
    result = check_output(to_json(RECORD))
    assert result.json_valid and result.schema_valid and result.record == RECORD


def test_guardrail_rejects_broken_json():
    result = check_output('{"company": "Clinique"')
    assert not result.json_valid and not result.schema_valid and result.record is None


def test_guardrail_explains_schema_errors():
    bad = {
        **RECORD,
        "need": "website_redesign",
        "budget_eur": "124 k€",
        "deadline": "fin février",
    }
    result = check_output(json.dumps(bad))
    assert result.json_valid and not result.schema_valid
    assert any("Need not in the list" in error for error in result.errors)
    assert any("Budget" in error for error in result.errors)
    assert any("Deadline" in error for error in result.errors)
    empty = check_output(json.dumps({key: None for key in RECORD}))
    assert any("Company missing" in error for error in empty.errors)


def test_parse_amounts_french_formats():
    assert parse_amounts("budget 124 k€, 297 000 euros, ~35k, 45 000 €, 1,2M") == {
        124000,
        297000,
        35000,
        45000,
        1200000,
    }
    assert parse_amounts("le 18e étage") == set()


def test_find_date_formats():
    assert find_date("2027-02-26", "échéance le 26/02/2027") is not None
    assert find_date("2027-02-26", "à livrer le 26 février 2027") is not None
    assert find_date("2027-02-26", "à livrer le 26 fevrier") is not None
    assert find_date("2027-03-01", "démarrage le 1er mars") is not None
    assert find_date("2027-02-26", "réunion le 12 mars") is None


def test_field_status():
    assert field_status("company", "Clinique Duchêne", NOTES) == FOUND
    assert field_status("contact_name", "Jean Dupont", NOTES) == CHECK
    assert field_status("budget_eur", 124000, NOTES) == FOUND
    assert field_status("budget_eur", 72000, NOTES) == CHECK
    assert field_status("deadline", "2027-02-26", NOTES) == FOUND
    assert field_status("deadline", "2027-12-12", NOTES) == CHECK
    assert field_status("need", "crm_migration", NOTES) == NOT_CHECKED
    assert field_status("contact_role", None, NOTES) == MISSING


def test_names_grounded_catches_invented_names():
    assert names_grounded(RECORD, NOTES)
    assert not names_grounded({**RECORD, "company": "Clinique Valmont"}, NOTES)
    assert not names_grounded(None, NOTES)


def test_format_value():
    assert format_value("budget_eur", 124000) == "€124,000"
    assert format_value("deadline", "2027-02-26") == "26 February 2027"
    assert format_value("need", "crm_migration") == "CRM migration"


def test_highlight_and_card():
    html = highlighted_notes_html(NOTES, RECORD)
    for tag in ("company", "contact", "role", "budget", "deadline"):
        assert tag in html
    assert "124 k€" in html and "<script" not in highlighted_notes_html(
        "<script>x</script>", RECORD
    )
    card = record_card_html(RECORD, NOTES)
    assert "CRM migration" in card and "26 February 2027" in card
