# =============================================================================
# Test local de l'évaluation CRM (sans GPU, sans GCP)
# =============================================================================
# Exécute le vrai code du composant `evaluation_component` sur des prédictions
# fabriquées à la main, et vérifie que ses copies du schéma restent alignées
# sur src/crm_schema.py.
# À lancer depuis la racine du projet :
#   uv run python local_tests/crm_metrics_test.py
# =============================================================================

import inspect
import re
import sys
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from src import crm_schema
from src.pipeline_components import (
    data_transformation_component as data_module,
)
from src.pipeline_components import (
    evaluation_component as eval_module,
)

REFERENCE = {
    "company": "Clinique Duchêne",
    "contact_name": "Camille Roux",
    "contact_role": "Directeur informatique",
    "need": "crm_migration",
    "budget_eur": 124000,
    "next_action": "involve_stakeholder",
    "deadline": "2027-02-26",
}
NO_OPTIONAL = {
    **REFERENCE,
    "contact_name": None,
    "contact_role": None,
    "budget_eur": None,
    "deadline": None,
}


def run_evaluation(rows: list[tuple[dict, str]]) -> tuple[pd.DataFrame, dict]:
    """Run the real evaluation component code on (reference, prediction) pairs."""
    tmp = Path(tempfile.mkdtemp())
    pd.DataFrame(
        {
            "user_input": ["note"] * len(rows),
            "reference": [crm_schema.to_json(ref) for ref, _ in rows],
            "extracted_response": [prediction for _, prediction in rows],
        }
    ).to_csv(tmp / "predictions.csv", index=False)
    logged: dict[str, float] = {}
    metrics = SimpleNamespace(
        log_metric=lambda name, value: logged.update({name: value})
    )
    evaluation_component = eval_module.evaluation_component.python_func
    evaluation_component(
        predictions=SimpleNamespace(path=str(tmp / "predictions.csv")),
        evaluation_results=SimpleNamespace(path=str(tmp / "results.csv")),
        metrics=metrics,
    )
    return pd.read_csv(tmp / "results.csv"), logged


def test_metrics() -> None:
    """Check the metrics on hand-made predictions."""
    perfect = crm_schema.to_json(REFERENCE)
    accent_case = crm_schema.to_json({**REFERENCE, "company": "CLINIQUE DUCHENE"})
    wrong_budget = crm_schema.to_json({**REFERENCE, "budget_eur": 12400})
    invented = crm_schema.to_json({**NO_OPTIONAL, "budget_eur": 50000})
    bad_enum = crm_schema.to_json({**REFERENCE, "need": "inconnu"})
    wrapped = f"Voici la fiche :\n```json\n{perfect}\n```"
    rows = [
        (REFERENCE, perfect),  # 0 parfait
        (REFERENCE, accent_case),  # 1 accents et casse ignorés
        (REFERENCE, wrong_budget),  # 2 un seul champ faux
        (NO_OPTIONAL, invented),  # 3 budget inventé
        (REFERENCE, "pas du json"),  # 4 JSON invalide
        (REFERENCE, bad_enum),  # 5 valeur hors liste fermée
        (REFERENCE, wrapped),  # 6 JSON entouré de texte, toléré
        (REFERENCE, ""),  # 7 réponse vide
    ]
    df, logged = run_evaluation(rows)
    assert df["valid_json"].tolist() == [1, 1, 1, 1, 0, 1, 1, 0]
    assert df["valid_schema"].tolist() == [1, 1, 1, 1, 0, 0, 1, 0]
    assert df["exact_match"].tolist() == [1, 1, 0, 0, 0, 0, 1, 0]
    assert df["field_budget_eur"].tolist() == [1, 1, 0, 0, 0, 1, 1, 0]
    assert df["field_need"].tolist() == [1, 1, 1, 1, 0, 0, 1, 0]
    assert df["hallucinated_field"].tolist() == [0, 0, 0, 1, 0, 0, 0, 0]
    assert logged["exact_match_mean"] == 3 / 8
    assert logged["valid_json_mean"] == 6 / 8
    assert (
        abs(logged["field_accuracy_mean"] - (7 + 7 + 6 + 6 + 0 + 6 + 7 + 0) / 56) < 1e-9
    )
    print("métriques OK :", {k: round(v, 3) for k, v in logged.items()})


def test_schema_copies_match() -> None:
    """The component copies of the schema must equal src/crm_schema.py."""
    source = inspect.getsource(eval_module.evaluation_component.python_func)
    assert re.search(r"fields = \[(.*?)\]", source, re.DOTALL)
    for name in crm_schema.FIELDS + crm_schema.NEEDS + crm_schema.NEXT_ACTIONS:
        assert f'"{name}"' in source, f"{name} absent du composant d'évaluation"
    # Aucune valeur en trop dans les listes fermées du composant
    block = source[source.index("needs = {") : source.index("deadline_re")]
    assert set(re.findall(r'"([a-z_]+)"', block)) == set(
        crm_schema.NEEDS + crm_schema.NEXT_ACTIONS
    )
    # La consigne de la préparation des données est identique mot pour mot :
    # on exécute la vraie instruction du composant au lieu de la relire en texte
    data_source = inspect.getsource(
        data_module.data_transformation_component.python_func
    )
    start = data_source.index("instruction = (")
    end = data_source.index("\n\n    def format_dataset_to_phi_messages")
    namespace: dict[str, str] = {}
    exec(textwrap.dedent(data_source[start:end]), namespace)  # noqa: S102
    assert namespace["instruction"] == crm_schema.INSTRUCTION
    print("copies du schéma alignées")


def test_data_transformation() -> None:
    """Run the real data transformation component on a tiny CSV."""
    tmp = Path(tempfile.mkdtemp())
    records = [{**REFERENCE, "company": f"Société {i}"} for i in range(20)]
    pd.DataFrame(
        {
            "note": [f"note numéro {i}" for i in range(20)],
            "record": [crm_schema.to_json(r) for r in records],
            "style": "bullets",
            "length": "short",
            "distractor": "none",
        }
    ).to_csv(tmp / "raw.csv", index=False)
    train, test = str(tmp / "train.csv"), str(tmp / "test.csv")
    data_module.data_transformation_component.python_func(
        raw_dataset_uri=str(tmp / "raw.csv"),
        train_test_split_ratio=0.25,
        train_dataset=train,
        test_dataset=test,
    )
    train_df, test_df = pd.read_csv(train), pd.read_csv(test)
    assert (len(train_df), len(test_df)) == (15, 5)
    assert list(train_df.columns) == ["style", "length", "distractor", "messages"]
    import ast

    messages = ast.literal_eval(re.sub(r"\}\s*\{", "}, {", train_df["messages"][0]))
    assert messages[0]["role"] == "user" and messages[1]["role"] == "assistant"
    assert messages[0]["content"].startswith(crm_schema.INSTRUCTION)
    assert crm_schema.parse_json(messages[1]["content"]) is not None
    print(
        "préparation des données OK :", len(train_df), "train /", len(test_df), "test"
    )


if __name__ == "__main__":
    test_metrics()
    test_schema_copies_match()
    test_data_transformation()
    print("\nTous les tests passent")
