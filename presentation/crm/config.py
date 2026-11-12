"""Configuration lue dans le fichier .env (voir .env.example)."""

import os
from pathlib import Path

from dotenv import load_dotenv

PRESENTATION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRESENTATION_ROOT.parent
DATA_DIR = PRESENTATION_ROOT / "data"
CONTENT_DIR = PRESENTATION_ROOT / "content"

# Même .env que le reste du projet (racine du repo)
load_dotenv(REPO_ROOT / ".env")

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION = os.getenv("GCP_REGION", "europe-west2")
GCP_PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "")
GCP_ENDPOINT_ID = os.getenv("GCP_ENDPOINT_ID", "")

# Nom et version (Model Registry) du modèle servi par l'endpoint, affichés et envoyés à Langfuse
MODEL_NAME = os.getenv("MODEL_NAME", "emeret-crm-phi3")
MODEL_VERSION = os.getenv("MODEL_VERSION", "1")

# La fiche JSON fait 58 à 92 tokens (mesuré sur le jeu de données) : 160 comme l'app Chainlit
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "160"))
REQUEST_TIMEOUT_S = int(os.getenv("REQUEST_TIMEOUT_S", "120"))

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_ENABLED = bool(
    os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
)
LANGFUSE_DASHBOARD_URL = os.getenv("LANGFUSE_DASHBOARD_URL", LANGFUSE_HOST)


def endpoint_configured() -> bool:
    return bool((GCP_PROJECT_NUMBER or GCP_PROJECT_ID) and GCP_ENDPOINT_ID)
