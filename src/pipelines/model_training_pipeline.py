"""Model training pipeline definition for Vertex AI."""

from kfp.dsl import pipeline

from src.pipeline_components.data_transformation_component import (
    data_transformation_component,
)


@pipeline()
def model_training_pipeline(
    raw_dataset_uri: str,
) -> None:
    """Model training pipeline definition."""
    data_transformation_component(
        train_test_split_ratio=0.1,
        raw_dataset_uri=raw_dataset_uri,
    )  # type: ignore
