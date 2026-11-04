"""Evaluation component for Vertex AI pipeline."""

from kfp.dsl import Dataset, Input, Metrics, Output, component


@component(
    # ragas a besoin de git, absent des images Python standard
    base_image="cicirello/pyaction:3.11",
    # Mêmes versions que dans notre .venv, où le code marche
    packages_to_install=[
        "ragas==0.4.3",
        # 0.4.2 a retiré un module que ragas 0.4.3 importe
        "langchain-community==0.4.1",
        "langchain==1.4.7",
        "langchain-core==1.7.2",
        "langchain-openai==1.7.3",
        "datasets==4.8.5",
        "rouge-score==0.1.2",
        "rapidfuzz==3.14.6",
        "pandas==3.0.6",
    ],
)
def evaluation_component(
    predictions: Input[Dataset],
    evaluation_results: Output[Dataset],
    metrics: Output[Metrics],
) -> None:
    """Score the predictions with ragas non-LLM metrics."""
    import logging
    import os

    # Pas d'envoi de statistiques d'usage à ragas depuis le cloud
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"

    import pandas as pd
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import ExactMatch, NonLLMStringSimilarity, RougeScore
    from ragas.metrics.base import SingleTurnMetric

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting evaluation process...")

    # -- Le code de local_tests/evaluation_test.py -----------------------------
    metric_definitions = [
        RougeScore(rouge_type="rougeL", mode="fmeasure"),
        # Pas de BleuScore : dans ragas 0.4.3 il ne compare que la 1re phrase
        NonLLMStringSimilarity(),
        ExactMatch(),
    ]

    def compute_metrics(
        user_input: str,
        response: str,
        reference: str,
        metric_definitions: list[SingleTurnMetric],
    ) -> dict[str, float | int]:
        """Compute metrics for a single prediction."""
        sample = SingleTurnSample(
            user_input=user_input, response=response, reference=reference
        )
        return {
            metric.name: metric.single_turn_score(sample) for metric in metric_definitions
        }

    def aggregate_metrics(per_sample_metrics: pd.DataFrame) -> dict[str, float]:
        """Aggregate metrics from per-sample metrics DataFrame."""
        means = per_sample_metrics.select_dtypes("number").mean()
        return {f"{name}_mean": float(value) for name, value in means.items()}

    # -- Scores par phrase -----------------------------------------------------
    logger.info(f"Reading predictions from {predictions.path}")
    predictions_df = pd.read_csv(predictions.path)
    predictions_df["extracted_response"] = predictions_df["extracted_response"].fillna("")

    results = []
    for row in predictions_df.itertuples():
        scores = compute_metrics(
            row.user_input, row.extracted_response, row.reference, metric_definitions
        )
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

    # -- Scores globaux, visibles dans la console Vertex AI --------------------
    aggregated = aggregate_metrics(per_sample_metrics)
    logger.info(f"Aggregated metrics: {aggregated}")
    for name, value in aggregated.items():
        metrics.log_metric(name, value)

    logger.info("Evaluation process completed successfully")
