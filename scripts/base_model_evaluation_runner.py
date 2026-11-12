"""Compile and submit the base model evaluation pipeline (baseline).

Usage (une seule fois : chaque lancement réserve un GPU) :
    uv run --env-file .env python -m scripts.base_model_evaluation_runner \
        --training-run model-training-pipeline-20261112183827
"""

import argparse

from google.cloud import aiplatform
from kfp import compiler

from src.constants import PIPELINE_ROOT_PATH, PROJECT_ID, PROJECT_NUMBER, REGION
from src.pipelines.base_model_evaluation_pipeline import (
    base_model_evaluation_pipeline,
)


def training_run_artifacts(run_name: str) -> dict[str, str]:
    """Find the model and test dataset URIs produced by a training pipeline run."""
    job = aiplatform.PipelineJob.get(
        f"projects/{PROJECT_NUMBER}/locations/{REGION}/pipelineJobs/{run_name}"
    )
    uris = {}
    for task in job.task_details:
        if task.task_name == "fine-tuning-component":
            uris["model_uri"] = task.outputs["model"].artifacts[0].uri
        if task.task_name == "data-transformation-component":
            uris["test_dataset_uri"] = task.outputs["test_dataset"].artifacts[0].uri
    return uris


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training-run", required=True, help="Nom du run d'entraînement"
    )
    args = parser.parse_args()

    aiplatform.init(project=PROJECT_ID, location=REGION)
    parameters = training_run_artifacts(args.training_run)
    print(parameters)

    pipeline_name = "base_model_evaluation_pipeline"
    compiler.Compiler().compile(
        pipeline_func=base_model_evaluation_pipeline,  # type: ignore
        package_path=f"{pipeline_name}.json",
    )
    job = aiplatform.PipelineJob(
        display_name=pipeline_name,
        template_path=f"{pipeline_name}.json",
        pipeline_root=f"gs://{PIPELINE_ROOT_PATH}",
        parameter_values=parameters,
    )
    job.submit()
