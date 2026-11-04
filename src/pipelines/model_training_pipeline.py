"""Model training pipeline definition for Vertex AI."""

from kfp.dsl import pipeline

from src.pipeline_components.data_transformation_component import (
    data_transformation_component,
)
from src.pipeline_components.evaluation_component import evaluation_component
from src.pipeline_components.fine_tuning_component import fine_tuning_component
from src.pipeline_components.inference_component import inference_component


@pipeline()
def model_training_pipeline(
    raw_dataset_uri: str,
) -> None:
    """Model training pipeline definition."""
    data_transformation_task = data_transformation_component(
        train_test_split_ratio=0.1,
        raw_dataset_uri=raw_dataset_uri,
    )  # type: ignore

    # Le train_dataset produit par l'étape 1 devient l'entrée du fine-tuning
    fine_tuning_task = fine_tuning_component(
        train_dataset=data_transformation_task.outputs["train_dataset"],
    )  # type: ignore
    # Machine avec un GPU NVIDIA T4, 16 CPU et 50 Go de mémoire
    fine_tuning_task.set_accelerator_type("NVIDIA_TESLA_T4")
    fine_tuning_task.set_cpu_limit("16")
    fine_tuning_task.set_memory_limit("50G")

    # Le modèle fine-tuné (étape 2) + le test_dataset (étape 1) -> prédictions
    inference_task = inference_component(
        model=fine_tuning_task.outputs["model"],
        test_dataset=data_transformation_task.outputs["test_dataset"],
    )  # type: ignore
    # GPU aussi pour l'inférence : générer avec Phi-3 sur CPU serait très lent
    inference_task.set_accelerator_type("NVIDIA_TESLA_T4")
    inference_task.set_cpu_limit("16")
    inference_task.set_memory_limit("50G")

    # Les prédictions (étape 3) -> scores ragas. Pas de GPU : ce sont des
    # calculs simples sur du texte
    evaluation_component(
        predictions=inference_task.outputs["predictions"],
    )  # type: ignore
