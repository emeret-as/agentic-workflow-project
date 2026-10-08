from kfp.dsl import pipeline

from src.pipeline_components.data_transformation_component import transform_data


@pipeline(
    name="model-training-pipeline",
    description="Prépare le dataset Yoda pour le fine-tuning de Phi-3",
)
def model_training_pipeline(
    input_path: str = "gs://emeret-llmops/yoda_sentences.csv",
    test_size: float = 0.2,
    seed: int = 42,
):
    # Étape unique : lecture, mise au format conversation et découpage train/test
    transform_data(input_path=input_path, test_size=test_size, seed=seed)
