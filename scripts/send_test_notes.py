"""Send meeting notes through the app's model call to fill Langfuse with real traces.

Chaque note passe par `answer()` de l'app Chainlit (même code, mêmes traces et
mêmes scores qu'un vrai utilisateur), puis la sortie est sauvegardée dans
`data/endpoint_outputs.json` (rejeu pour la démo, analyse des erreurs).

Deux jeux de notes :
- les 56 notes de test du pipeline (avec leur fiche de référence : on ajoute
  le score `exact_match` à la trace) ;
- quelques notes « pièges » écrites à la main (hors distribution), pour voir
  ce que le monitoring et le juge LLM attrapent.

Usage (endpoint déployé, GCP_ENDPOINT_ID et LANGFUSE_* dans .env) :
    PYTHONPATH=. uv run --env-file .env python -m scripts.send_test_notes \
        --eval-results gs://.../evaluation-component_.../evaluation_results
"""

import argparse
import csv
import io
import json
import time
from pathlib import Path
from typing import Any

from google.cloud import storage

from src.app import main as app
from src.constants import PROJECT_ID, PROJECT_ROOT_PATH
from src.crm_schema import FIELDS, INSTRUCTION, is_valid_record, normalize, parse_json

OUTPUT_PATH = PROJECT_ROOT_PATH / "data" / "endpoint_outputs.json"

# Notes hors distribution : chacune teste une limite précise du modèle
EDGE_CASES: list[dict[str, str]] = [
    {
        "id": "anglais",
        "why": "Note en anglais (le modèle n'a vu que du français)",
        "note": "Call with Mark Evans (CTO, Brightwave Ltd). They want to move "
        "their apps to AWS, budget around 80k GBP, decision by end of Q1. "
        "Next step: send them a proposal.",
    },
    {
        "id": "vide",
        "why": "Aucune information exploitable",
        "note": "Réunion annulée, à reprogrammer.",
    },
    {
        "id": "hors-sujet",
        "why": "Texte qui n'est pas une note commerciale",
        "note": "Recette : faire revenir les oignons 10 minutes, ajouter la "
        "crème et laisser mijoter à feu doux.",
    },
    {
        "id": "deux-entreprises",
        "why": "Deux entreprises dans la même note",
        "note": "Déjeuner avec Paul Martin (DAF, Groupe Lavaud) et Inès Kader de "
        "Solvia. Lavaud veut un tableau de bord financier, Solvia hésite encore. "
        "On envoie la doc aux deux.",
    },
    {
        "id": "abreviations",
        "why": "Montant abrégé et date relative",
        "note": "Tel rapide avec Mme Girard, responsable achats chez Transports "
        "Morel : besoin de former 40 chauffeurs à l'outil, ~35k, à boucler avant "
        "fin janvier. Je leur cale une démo mardi.",
    },
    {
        "id": "besoin-hors-liste",
        "why": "Besoin absent de la liste fermée",
        "note": "RDV avec Hugo Lambert, gérant de la Boulangerie Lambert : il veut "
        "refaire son site vitrine. Pas de budget défini. Je lui envoie un devis.",
    },
    {
        "id": "dictee-bruitee",
        "why": "Dictée vocale avec hésitations",
        "note": "euh donc j'ai vu euh Sandrine Perret chez Optique Vision Plus elle "
        "est directrice des opérations euh ils veulent automatiser la facturation "
        "enfin les relances quoi budget je sais pas elle m'a dit genre cinquante "
        "mille et faut que ce soit fait pour juin on se rappelle la semaine pro",
    },
]


def load_test_notes(eval_results_uri: str) -> list[dict[str, Any]]:
    """Read the pipeline's evaluation results (test notes + reference records)."""
    bucket, blob = eval_results_uri.removeprefix("gs://").split("/", 1)
    text = (
        storage.Client(project=PROJECT_ID)
        .bucket(bucket)
        .blob(blob)
        .download_as_text(encoding="utf-8")
    )
    rows = list(csv.DictReader(io.StringIO(text)))
    return [
        {
            "id": f"test-{index:02d}",
            "note": row["user_input"].removeprefix(INSTRUCTION),
            "reference": json.loads(row["reference"]),
        }
        for index, row in enumerate(rows)
    ]


def exact_match(record: dict[str, Any] | None, reference: dict[str, Any]) -> bool:
    """Same rule as the pipeline's evaluation: every field equal after normalize."""
    return record is not None and all(
        normalize(record.get(field)) == normalize(reference.get(field))
        for field in FIELDS
    )


def run_note(item: dict[str, Any], source: str) -> dict[str, Any]:
    """Send one note through the app and return what was observed."""
    trace_id = app.langfuse.create_trace_id()
    started_at = time.perf_counter()
    # langfuse_trace_id : argument spécial du décorateur @observe (SDK v3)
    extracted = app.answer(item["note"], langfuse_trace_id=trace_id)
    latency = time.perf_counter() - started_at
    record = parse_json(extracted)
    result = {
        **item,
        "source": source,
        "trace_id": trace_id,
        "output": extracted,
        "valid_record": is_valid_record(record),
        "latency_seconds": round(latency, 2),
    }
    app.langfuse.create_score(
        name="source", value=source, trace_id=trace_id, data_type="CATEGORICAL"
    )
    if "reference" in item:
        result["exact_match"] = exact_match(record, item["reference"])
        app.langfuse.create_score(
            name="exact_match",
            value=float(result["exact_match"]),
            trace_id=trace_id,
            data_type="NUMERIC",
        )
    return result


def main() -> None:
    """Send the test notes then the edge cases, and save every output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-results", required=True, help="gs:// du CSV d'évaluation"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Nombre de notes de test"
    )
    args = parser.parse_args()

    test_notes = load_test_notes(args.eval_results)[: args.limit]
    results = []
    for source, items in (("test", test_notes), ("piege", EDGE_CASES)):
        for item in items:
            result = run_note(item, source)
            results.append(result)
            status = "ok" if result["valid_record"] else "INVALIDE"
            print(f"{result['id']:<20} {status:<9} {result['latency_seconds']:>6.2f} s")
    app.langfuse.flush()

    Path(OUTPUT_PATH).write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tests = [r for r in results if r["source"] == "test"]
    print(
        f"{len(results)} notes envoyées, exact_match test = "
        f"{sum(r['exact_match'] for r in tests)}/{len(tests)} -> {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
