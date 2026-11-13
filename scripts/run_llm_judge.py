"""Run the LLM judge on every Langfuse trace that has no `fidelite_fiche` score yet.

Lit les spans `User Message` (note en entrée, fiche en sortie) par l'API publique
de Langfuse v4, fait juger chaque fiche par Gemini (src/llm_judge.py) et envoie
le score sur la trace. Relançable sans risque : les traces déjà notées sont sautées.

Usage :
    PYTHONPATH=. uv run --env-file .env python -m scripts.run_llm_judge
"""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests
from langfuse import get_client

from src.llm_judge import SCORE_NAME, client, judge

APP_SPAN = "User Message"


def api_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        f"{os.environ['LANGFUSE_HOST'].rstrip('/')}/api/public/{path}",
        params=params,
        auth=(os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"]),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def paginate(path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """All items of a cursor-paginated Langfuse endpoint."""
    items, cursor = [], None
    while True:
        page = api_get(path, {**params, **({"cursor": cursor} if cursor else {})})
        items += page["data"]
        cursor = (page.get("meta") or {}).get("cursor")
        if not cursor or not page["data"]:
            return items


def as_text(value: Any) -> str:
    """Span input/output as plain text (the SDK may store a string or a list)."""
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def main() -> None:
    spans = paginate(
        "v2/observations", {"name": APP_SPAN, "limit": 100, "fields": "core,io"}
    )
    scores = paginate(
        "v3/scores", {"limit": 100, "name": SCORE_NAME, "fields": "core,subject"}
    )
    judged = {(score.get("subject") or {}).get("id") for score in scores}
    todo = [
        span for span in spans if span["traceId"] not in judged and span.get("output")
    ]
    print(f"{len(spans)} traces, {len(todo)} à juger")

    langfuse = get_client()

    def run(span: dict[str, Any]) -> float | None:
        try:
            score, reason = judge(as_text(span["input"]), as_text(span["output"]))
        except Exception as error:  # noqa: BLE001  une erreur Gemini ne bloque pas les autres
            print(f"{span['traceId'][:8]} non jugée : {error}")
            return None
        langfuse.create_score(
            name=SCORE_NAME,
            value=score,
            trace_id=span["traceId"],
            data_type="NUMERIC",
            comment=reason,
        )
        return score

    client()  # client Gemini créé une seule fois, avant les threads
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, todo))
    langfuse.flush()
    results = [score for score in results if score is not None]
    if results:
        print(
            f"{len(results)} traces notées : "
            f"{results.count(1.0)} à 1, {results.count(0.5)} à 0,5, {results.count(0.0)} à 0"
        )


if __name__ == "__main__":
    main()
