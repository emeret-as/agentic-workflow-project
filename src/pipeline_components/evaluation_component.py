"""Evaluation component for Vertex AI pipeline."""

from kfp.dsl import Dataset, Input, Metrics, Output, component


@component(
    base_image="python:3.11-slim",
    # Aucune bibliothèque d'évaluation : les métriques sont déterministes
    # (JSON valide, champs exacts) et tiennent en quelques lignes.
    packages_to_install=["pandas==3.0.6"],
)
def evaluation_component(
    predictions: Input[Dataset],
    evaluation_results: Output[Dataset],
    metrics: Output[Metrics],
) -> None:
    """Score the predicted CRM records against the reference records."""
    import json
    import logging
    import re
    import unicodedata

    import pandas as pd

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting evaluation process...")

    # -- Copie de `src/crm_schema.py` (un composant Kubeflow est autonome) -----
    fields = [
        "company",
        "contact_name",
        "contact_role",
        "need",
        "budget_eur",
        "next_action",
        "deadline",
    ]
    needs = {
        "crm_migration",
        "data_platform",
        "cybersecurity",
        "cloud_migration",
        "ai_assistant",
        "process_automation",
        "analytics_dashboard",
        "team_training",
    }
    next_actions = {
        "send_proposal",
        "schedule_demo",
        "send_documentation",
        "schedule_followup_call",
        "involve_stakeholder",
        "internal_review",
    }
    deadline_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def parse_json(text: str) -> dict | None:
        """Extract the first JSON object found in a model output."""
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def is_valid_record(record: dict | None) -> bool:
        """Check keys, types and closed lists of a record."""
        if record is None or list(record) != fields:
            return False
        if not isinstance(record["company"], str) or not record["company"].strip():
            return False
        for name in ("contact_name", "contact_role"):
            value = record[name]
            if value is not None and not (isinstance(value, str) and value.strip()):
                return False
        budget = record["budget_eur"]
        if budget is not None and not (
            isinstance(budget, int) and not isinstance(budget, bool) and budget > 0
        ):
            return False
        deadline = record["deadline"]
        if deadline is not None and not (
            isinstance(deadline, str) and deadline_re.match(deadline)
        ):
            return False
        return record["need"] in needs and record["next_action"] in next_actions

    def normalize(value):
        """Normalize a field value for comparison (case, accents, spaces)."""
        if isinstance(value, str):
            decomposed = unicodedata.normalize("NFKD", value)
            stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
            return " ".join(stripped.split()).casefold()
        return value

    # -- Scores par note --------------------------------------------------------
    logger.info(f"Reading predictions from {predictions.path}")
    predictions_df = pd.read_csv(predictions.path)
    predictions_df["extracted_response"] = predictions_df["extracted_response"].fillna(
        ""
    )

    results = []
    for row in predictions_df.itertuples():
        reference = parse_json(row.reference) or {}
        predicted = parse_json(row.extracted_response)
        valid_json = predicted is not None
        valid_record = is_valid_record(predicted)
        scores = {
            "valid_json": int(valid_json),
            "valid_schema": int(valid_record),
        }
        # Un champ est juste s'il vaut la référence (accents et casse ignorés).
        # Si le JSON est invalide, tous les champs comptent comme faux.
        field_hits = {}
        for name in fields:
            hit = valid_json and normalize(predicted.get(name)) == normalize(
                reference.get(name)
            )
            field_hits[name] = int(hit)
            scores[f"field_{name}"] = int(hit)
        scores["exact_match"] = int(all(field_hits.values()))
        # Champ inventé : le modèle donne une valeur alors que la référence est null
        nullable_halluc = [
            int(
                valid_json
                and reference.get(name) is None
                and predicted.get(name) is not None
            )
            for name in ("contact_name", "contact_role", "budget_eur", "deadline")
        ]
        scores["hallucinated_field"] = int(any(nullable_halluc))
        results.append(
            {
                "user_input": row.user_input,
                "reference": row.reference,
                "extracted_response": row.extracted_response,
                **scores,
            }
        )
    per_sample_metrics = pd.DataFrame(results)

    logger.info(f"Writing per-sample results to {evaluation_results.path}")
    per_sample_metrics.to_csv(evaluation_results.path, index=False)

    # -- Scores globaux, visibles dans la console Vertex AI ---------------------
    means = per_sample_metrics.select_dtypes("number").mean()
    aggregated = {f"{name}_mean": float(value) for name, value in means.items()}
    # Part de champs corrects sur l'ensemble des notes (7 champs par note)
    aggregated["field_accuracy_mean"] = float(
        per_sample_metrics[[f"field_{name}" for name in fields]].to_numpy().mean()
    )
    logger.info(f"Aggregated metrics: {aggregated}")
    for name, value in aggregated.items():
        metrics.log_metric(name, value)

    logger.info("Evaluation process completed successfully")
