"""Appel du modèle déployé sur un endpoint Vertex AI."""

import google.auth
import requests
from google.auth.transport.requests import Request

from crm import config

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class EndpointError(RuntimeError):
    """Erreur lisible à afficher dans l'interface."""


def _access_token() -> str:
    """Jeton Google redemandé à chaque appel : il expire au bout d'environ 1 h."""
    try:
        credentials, _ = google.auth.default(scopes=_SCOPES)
        credentials.refresh(Request())
    except Exception as error:  # pas de compte Google configuré, réseau…
        raise EndpointError(
            "Could not get a Google token. Run `gcloud auth application-default login`."
        ) from error
    return credentials.token


def endpoint_url() -> str:
    return (
        f"https://{config.GCP_REGION}-aiplatform.googleapis.com/v1/projects/"
        f"{config.GCP_PROJECT_NUMBER or config.GCP_PROJECT_ID}/locations/{config.GCP_REGION}/endpoints/"
        f"{config.GCP_ENDPOINT_ID}:predict"
    )


def generation_parameters() -> dict:
    return {"max_new_tokens": config.MAX_NEW_TOKENS, "do_sample": False}


def call_endpoint(prompt: str) -> str:
    """Envoie le prompt à l'endpoint et renvoie le texte brut généré."""
    if not config.endpoint_configured():
        raise EndpointError(
            "Endpoint not configured: set GCP_PROJECT_NUMBER and GCP_ENDPOINT_ID in .env."
        )
    payload = {"instances": [{"input": prompt}], "parameters": generation_parameters()}
    try:
        response = requests.post(
            endpoint_url(),
            headers={"Authorization": f"Bearer {_access_token()}"},
            json=payload,
            timeout=config.REQUEST_TIMEOUT_S,
        )
    except requests.Timeout as error:
        raise EndpointError(
            f"No answer from the endpoint after {config.REQUEST_TIMEOUT_S} s."
        ) from error
    except requests.RequestException as error:
        raise EndpointError(f"Endpoint unreachable: {error}") from error
    if response.status_code != 200:
        raise EndpointError(
            f"The endpoint answered {response.status_code}: {response.text[:300]}"
        )
    predictions = response.json().get("predictions") or []
    if not predictions:
        raise EndpointError("Empty answer from the endpoint.")
    return str(predictions[0])
