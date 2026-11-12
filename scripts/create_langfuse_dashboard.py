"""Create the CRM monitoring dashboard in Langfuse through its public API.

Session 5 : le cours crée le dashboard à la main dans l'interface. On le
décrit ici en code (API « unstable » de Langfuse v4) pour pouvoir le recréer à
l'identique sur un autre poste. Il reste modifiable dans l'interface.

Usage (Langfuse lancé, LANGFUSE_* dans .env) :
    uv run --env-file .env python -m scripts.create_langfuse_dashboard
"""

import os
from typing import Any

import requests

DASHBOARD_NAME = "Fiches CRM - suivi en production"
ENDPOINT_GENERATION = "Vertex AI endpoint"  # nom de la generation dans l'app
APP_SPAN = "User Message"  # nom du span racine dans l'app


def name_is(value: str) -> list[dict[str, str]]:
    """Filter on the observation (or score) name."""
    return [{"column": "name", "operator": "=", "value": value, "type": "string"}]


WIDGETS: list[dict[str, Any]] = [
    {
        "name": "Notes traitées",
        "description": "Nombre de notes envoyées à l'app sur la période.",
        "view": "observations",
        "dimensions": [],
        "metrics": [{"measure": "count", "agg": "count"}],
        "filters": name_is(APP_SPAN),
        "chartType": "NUMBER",
    },
    {
        "name": "Qualité des fiches",
        "description": "Moyenne de chaque score : json_valid, schema_valid, "
        "names_grounded (calculés par l'app), exact_match (jeu de test), "
        "fidelite_fiche (juge LLM).",
        "view": "scores-numeric",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "value", "agg": "avg"}],
        "filters": [],
        "chartType": "HORIZONTAL_BAR",
    },
    {
        "name": "Qualité dans le temps",
        "description": "Une baisse signale des notes qui s'éloignent des données "
        "d'entraînement (dérive).",
        "view": "scores-numeric",
        "dimensions": [{"field": "name"}],
        "metrics": [{"measure": "value", "agg": "avg"}],
        "filters": [],
        "chartType": "LINE_TIME_SERIES",
    },
    {
        "name": "Latence de l'endpoint (p50, p95)",
        "description": "Temps de réponse de l'endpoint Vertex AI, en secondes.",
        "view": "observations",
        "dimensions": [],
        "metrics": [
            {"measure": "latency", "agg": "p50"},
            {"measure": "latency", "agg": "p95"},
        ],
        "filters": name_is(ENDPOINT_GENERATION),
        "chartType": "LINE_TIME_SERIES",
    },
]


def api(method: str, path: str, **kwargs: Any) -> Any:
    """Call the Langfuse public API with the project keys."""
    response = requests.request(
        method,
        f"{os.environ['LANGFUSE_HOST'].rstrip('/')}/api/public/unstable/{path}",
        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]),
        timeout=30,
        **kwargs,
    )
    if not response.ok:
        raise SystemExit(f"{method} {path} -> {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    """Create the widgets, then the dashboard holding them (skip if it exists)."""
    existing = api("GET", "dashboards", params={"limit": 100})["data"]
    if any(dashboard["name"] == DASHBOARD_NAME for dashboard in existing):
        print(f"Le dashboard {DASHBOARD_NAME!r} existe déjà : rien à faire")
        return

    dashboard = api(
        "POST",
        "dashboards",
        json={"name": DASHBOARD_NAME, "description": "Monitoring de l'app CRM"},
    )
    for widget in WIDGETS:
        created = api("POST", "dashboard-widgets", json=widget)
        api(
            "POST",
            f"dashboards/{dashboard['id']}/placements",
            json={"type": "widget", "widgetId": created["id"]},
        )
        print(f"Widget ajouté : {widget['name']}")
    print(f"Dashboard créé : {dashboard['id']}")


if __name__ == "__main__":
    main()
