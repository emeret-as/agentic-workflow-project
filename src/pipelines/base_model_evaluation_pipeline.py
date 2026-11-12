"""Baseline pipeline: evaluate Phi-3 without fine-tuning on the same test notes.

Réutilise les artefacts d'un run du pipeline d'entraînement (dossier du modèle,
pour le tokenizer et l'identifiant du modèle de base, et le test_dataset), puis
lance les mêmes composants d'inférence et d'évaluation. Les métriques sont donc
directement comparables à celles du modèle fine-tuné.
"""

from kfp import dsl
from kfp.dsl import pipeline

from src.pipeline_components.evaluation_component import evaluation_component
from src.pipeline_components.inference_component import inference_component


@pipeline()
def base_model_evaluation_pipeline(model_uri: str, test_dataset_uri: str) -> None:
    """Inference + evaluation of the base model on an existing test split."""
    model_importer = dsl.importer(
        artifact_uri=model_uri, artifact_class=dsl.Model, reimport=False
    )
    test_dataset_importer = dsl.importer(
        artifact_uri=test_dataset_uri, artifact_class=dsl.Dataset, reimport=False
    )

    inference_task = inference_component(
        model=model_importer.output,
        test_dataset=test_dataset_importer.output,
        use_base_model=True,
    )  # type: ignore
    # Même machine que l'inférence du pipeline d'entraînement
    inference_task.set_accelerator_type("NVIDIA_TESLA_T4")
    inference_task.set_cpu_limit("16")
    inference_task.set_memory_limit("50G")

    evaluation_component(
        predictions=inference_task.outputs["predictions"],
    )  # type: ignore
