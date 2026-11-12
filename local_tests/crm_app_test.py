# =============================================================================
# Test local de l'app Chainlit CRM (faux endpoint, sans GCP ni GPU)
# =============================================================================
# À lancer depuis la racine du projet :
#   uv run --env-file .env python local_tests/crm_app_test.py
# =============================================================================

import os
import sys
from pathlib import Path

os.environ.setdefault("GCP_PROJECT_NUMBER", "123")
os.environ.setdefault("GCP_ENDPOINT_ID", "456")
os.environ["OTEL_SDK_DISABLED"] = "true"  # pas d'envoi vers Langfuse pendant le test
sys.path.insert(0, str(Path(__file__).parents[1]))

import google.auth.credentials

from src.app import main as app
from src.crm_schema import INSTRUCTION, to_json

NOTE = (
    "Appel avec Camille Roux, Directeur informatique chez Clinique Duchêne. "
    "Ils veulent migrer leur CRM, budget 124 k€, échéance le 26/02/2027. "
    "Prochaine étape : inviter leur sponsor au prochain échange."
)
GOOD = {
    "company": "Clinique Duchêne",
    "contact_name": "Camille Roux",
    "contact_role": "Directeur informatique",
    "need": "crm_migration",
    "budget_eur": 124000,
    "next_action": "involve_stakeholder",
    "deadline": "2027-02-26",
}


def wrap(text: str) -> str:
    """Wrap a model answer the way the handler returns it."""
    return f"<|user|> x<|end|><|assistant|> {text}<|end|><|endoftext|>"


def test_prompt_and_extraction() -> None:
    """The prompt matches the training format; extraction handles all endings."""
    prompt = app.build_prompt(NOTE)
    assert prompt == f"<|user|>\n{INSTRUCTION}{NOTE}<|end|>\n<|assistant|>\n"
    assert app.extract_response(wrap(to_json(GOOD))) == to_json(GOOD)
    assert app.extract_response("<|assistant|> coupé") == "coupé"
    assert app.extract_response("rien") == ""


def test_scores() -> None:
    """Reference-free scores catch invalid JSON and invented names."""
    ok = app.score_output(NOTE, to_json(GOOD))
    assert ok == {"json_valid": 1.0, "schema_valid": 1.0, "names_grounded": 1.0}
    invented = app.score_output(NOTE, to_json({**GOOD, "contact_name": "Jean Dupont"}))
    assert invented == {"json_valid": 1.0, "schema_valid": 1.0, "names_grounded": 0.0}
    bad_enum = app.score_output(NOTE, to_json({**GOOD, "need": "autre"}))
    assert bad_enum == {"json_valid": 1.0, "schema_valid": 0.0, "names_grounded": 0.0}
    broken = app.score_output(NOTE, '{"company": "X", ')
    assert broken == {"json_valid": 0.0, "schema_valid": 0.0, "names_grounded": 0.0}
    # accents et casse ne comptent pas comme une hallucination
    accent = app.score_output(NOTE, to_json({**GOOD, "company": "CLINIQUE DUCHENE"}))
    assert accent["names_grounded"] == 1.0


def test_answer_with_fake_endpoint() -> None:
    """End to end through answer() with a fake Vertex AI response."""
    sent: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None: ...
        def json(self) -> dict:
            return {
                "predictions": [wrap(to_json(GOOD))],
                "modelDisplayName": "m",
                "modelVersionId": "1",
            }

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, json=json)
        return FakeResponse()

    app.requests.post = fake_post
    app.get_access_token = lambda: "tok"
    assert app.answer(NOTE) == to_json(GOOD)
    assert sent["headers"]["Authorization"] == "Bearer tok"
    assert sent["json"]["instances"][0]["input"] == app.build_prompt(NOTE)
    assert sent["json"]["parameters"]["max_new_tokens"] == 160
    assert sent["url"] == app.ENDPOINT_URL and sent["url"].endswith(":predict")


def test_display() -> None:
    """Valid records are shown as JSON, invalid ones with a visible warning."""
    shown = app.format_answer(to_json(GOOD))
    assert shown.startswith("```json") and '"company": "Clinique Duchêne"' in shown
    assert "n'est pas valide" in app.format_answer("pas du json")
    assert "n'est pas valide" in app.format_answer(to_json({**GOOD, "need": "autre"}))


def test_credentials_are_adc() -> None:
    """The app authenticates with ADC (no gcloud subprocess)."""
    assert isinstance(app._credentials, google.auth.credentials.Credentials)


if __name__ == "__main__":
    test_prompt_and_extraction()
    test_scores()
    test_answer_with_fake_endpoint()
    test_display()
    test_credentials_are_adc()
    print("app CRM : tous les tests passent")
