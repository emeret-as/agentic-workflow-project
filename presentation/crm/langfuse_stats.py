"""Chiffres de monitoring lus en direct dans Langfuse (API publique v4).

La page Monitoring les affiche au lieu d'une capture d'écran : ils bougent dès
qu'une nouvelle fiche est remplie pendant la démo.
"""

import os
from collections import Counter, defaultdict
from statistics import median
from typing import Any

import requests

from crm import config

APP_SPAN = "User Message"
ENDPOINT_GENERATION = "Vertex AI endpoint"
JUDGE_SCORE = "fidelite_fiche"


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"{config.LANGFUSE_HOST.rstrip('/')}/api/public/{path}",
        params=params,
        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _all(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    items, cursor = [], None
    while True:
        page = _get(path, {**params, **({"cursor": cursor} if cursor else {})})
        items += page["data"]
        cursor = (page.get("meta") or {}).get("cursor")
        if not cursor or not page["data"]:
            return items


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def fetch_stats() -> dict[str, Any]:
    """Traces, average of each numeric score, judge verdicts and endpoint latency."""
    traces = _all("v2/observations", {"name": APP_SPAN, "limit": 100, "fields": "core"})
    calls = _all(
        "v2/observations", {"name": ENDPOINT_GENERATION, "limit": 100, "fields": "core"}
    )
    scores = _all("v3/scores", {"limit": 100, "fields": "core"})

    values: dict[str, list[float]] = defaultdict(list)
    for score in scores:
        if (
            score.get("dataType") in ("NUMERIC", "BOOLEAN")
            and score.get("value") is not None
        ):
            values[score["name"]].append(float(score["value"]))
    latencies = [float(call["latency"]) for call in calls if call.get("latency")]
    return {
        "traces": len(traces),
        "scores": {name: (sum(v) / len(v), len(v)) for name, v in values.items()},
        "judge": Counter(values.get(JUDGE_SCORE, [])),
        "latency_p50": median(latencies) if latencies else None,
        "latency_p95": _percentile(latencies, 0.95) if latencies else None,
    }
