"""Pipeline compilation and submission utilities for Vertex AI."""

from google.cloud import aiplatform
from kfp import compiler

from src.constants import (
    PIPELINE_ROOT_PATH,
    PROJECT_ID,
    RAW_DATASET_URI,
    REGION,
)
from src.pipelines.model_training_pipeline import model_training_pipeline

if __name__ == "__main__":
    aiplatform.init(project=PROJECT_ID, location=REGION)

    pipeline_name = "model_training_pipeline"
    compiler.Compiler().compile(
        pipeline_func=model_training_pipeline,  # type: ignore
        package_path=f"{pipeline_name}.json",
    )
    job = aiplatform.PipelineJob(
        display_name=pipeline_name,
        template_path=f"{pipeline_name}.json",
        pipeline_root=f"gs://{PIPELINE_ROOT_PATH}",
        parameter_values={"raw_dataset_uri": RAW_DATASET_URI},
    )
    job.submit()
