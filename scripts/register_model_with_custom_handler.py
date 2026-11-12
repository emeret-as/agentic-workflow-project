"""Register a fine-tuned model in the Vertex AI Model Registry with a custom handler.

Usage :
    uv run --env-file .env python -m scripts.register_model_with_custom_handler \
        --model-uri gs://emeret-llmops/vertexai-pipeline-root/.../model \
        --model-name emeret-ureboullet_model

Pour enregistrer une nouvelle version d'un modèle existant, passer
`--parent-model` (ID ou nom de ressource du modèle parent).
"""

import argparse
from pathlib import Path

from google.cloud import aiplatform, storage

from src.constants import PROJECT_ID, PROJECT_ROOT_PATH, REGION

# Image Hugging Face prébuilt pour Vertex AI (imposée par l'énoncé)
SERVING_CONTAINER_IMAGE_URI = (
    "us-docker.pkg.dev/deeplearning-platform-release/gcr.io/"
    "huggingface-pytorch-inference-cu121.2-3.transformers.4-46.ubuntu2204.py311"
)
# Le conteneur attend le handler à la racine du dossier des artefacts
HANDLER_LOCAL_PATH = PROJECT_ROOT_PATH / "src" / "handler.py"
HANDLER_BLOB_NAME = "handler.py"


def upload_handler(model_uri: str, handler_path: Path = HANDLER_LOCAL_PATH) -> None:
    """Upload handler.py at the root of the model artifacts folder in GCS."""
    bucket_name, prefix = model_uri.removeprefix("gs://").split("/", 1)
    blob_name = f"{prefix.rstrip('/')}/{HANDLER_BLOB_NAME}"
    blob = storage.Client().bucket(bucket_name).blob(blob_name)
    blob.upload_from_filename(str(handler_path))
    print(f"Handler uploaded to gs://{bucket_name}/{blob_name}")


def register_model(
    model_uri: str,
    model_name: str,
    parent_model: str | None = None,
    description: str | None = None,
) -> aiplatform.Model:
    """Register the model (or a new version of it) in the Vertex AI Model Registry."""
    return aiplatform.Model.upload(
        display_name=model_name,
        description=description,
        artifact_uri=model_uri.rstrip("/"),
        serving_container_image_uri=SERVING_CONTAINER_IMAGE_URI,
        # Port sur lequel Vertex AI envoie les requêtes au conteneur
        serving_container_ports=[8080],
        parent_model=parent_model,
        is_default_version=True,
    )


def main() -> None:
    """Upload the custom handler then register the model."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-uri", required=True, help="gs:// URI du dossier `model` du pipeline"
    )
    parser.add_argument("--model-name", required=True, help="Nom affiché du modèle")
    parser.add_argument(
        "--parent-model",
        default=None,
        help="Modèle existant dont on crée une nouvelle version",
    )
    parser.add_argument("--description", default=None)
    args = parser.parse_args()

    aiplatform.init(project=PROJECT_ID, location=REGION)

    # 1. Handler d'abord : il doit être dans les artefacts avant l'enregistrement
    upload_handler(args.model_uri)
    # 2. Enregistrement dans le Model Registry
    model = register_model(
        args.model_uri, args.model_name, args.parent_model, args.description
    )
    print(f"Model registered: {model.resource_name} (version {model.version_id})")


if __name__ == "__main__":
    main()
