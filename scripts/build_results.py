"""Gather the evaluation results of both models for the presentation app.

Lit dans Vertex AI les métriques des deux pipelines (modèle fine-tuné et
Phi-3 de base), et leurs fichiers `evaluation_results` dans GCS. Il découpe les
résultats par style, longueur et élément parasite des notes (colonnes du CSV),
puis écrit `presentation/data/results.json`.

Usage :
    uv run --env-file .env python -m scripts.build_results \
        --finetuned-run model-training-pipeline-20261112183827 \
        --base-run base-model-evaluation-pipeline-20261112212113
"""

import argparse
import csv
import io
import json
from collections import defaultdict
from typing import Any

from google.cloud import aiplatform, storage

from src.constants import PROJECT_ID, PROJECT_NUMBER, PROJECT_ROOT_PATH, REGION
from src.crm_schema import INSTRUCTION

OUTPUT_PATH = PROJECT_ROOT_PATH / "presentation" / "data" / "results.json"
DATASET_PATH = PROJECT_ROOT_PATH / "data" / "crm_meeting_notes.csv"
ENDPOINT_OUTPUTS_PATH = PROJECT_ROOT_PATH / "data" / "endpoint_outputs.json"
GROUP_COLUMNS = ("distractor", "style", "length")


def run_outputs(run_name: str) -> dict[str, Any]:
    """Metrics of the evaluation step, its results file, and the training metrics."""
    job = aiplatform.PipelineJob.get(
        f"projects/{PROJECT_NUMBER}/locations/{REGION}/pipelineJobs/{run_name}"
    )
    outputs: dict[str, Any] = {"run": run_name}
    for task in job.task_details:
        if task.task_name == "evaluation-component":
            outputs["metrics"] = dict(task.outputs["metrics"].artifacts[0].metadata)
            outputs["results_uri"] = task.outputs["evaluation_results"].artifacts[0].uri
        if task.task_name == "fine-tuning-component":
            outputs["training"] = dict(task.outputs["metrics"].artifacts[0].metadata)
    return outputs


def read_results(uri: str) -> list[dict[str, str]]:
    """Read an evaluation_results CSV from GCS."""
    bucket, blob = uri.removeprefix("gs://").split("/", 1)
    text = (
        storage.Client(project=PROJECT_ID)
        .bucket(bucket)
        .blob(blob)
        .download_as_text(encoding="utf-8")
    )
    return list(csv.DictReader(io.StringIO(text)))


def note_of(row: dict[str, str]) -> str:
    """The raw note of an evaluation row (the instruction removed)."""
    return row["user_input"].removeprefix(INSTRUCTION)


def breakdown(rows: list[dict[str, str]], meta: dict[str, dict]) -> dict[str, Any]:
    """Exact-match rate per value of each note attribute (style, length, distractor)."""
    groups: dict[str, Any] = {}
    for column in GROUP_COLUMNS:
        counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in rows:
            value = meta[note_of(row)][column]
            counts[value][0] += 1
            counts[value][1] += int(row["exact_match"])
        groups[column] = {
            value: {"n": n, "exact": ok} for value, (n, ok) in sorted(counts.items())
        }
    return groups


def main() -> None:
    """Build results.json from both pipeline runs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finetuned-run", required=True)
    parser.add_argument("--base-run", required=True)
    args = parser.parse_args()

    aiplatform.init(project=PROJECT_ID, location=REGION)
    with open(DATASET_PATH, encoding="utf-8") as file:
        meta = {row["note"]: row for row in csv.DictReader(file)}

    models, rows_by_model = {}, {}
    for key, run_name in (("finetuned", args.finetuned_run), ("base", args.base_run)):
        outputs = run_outputs(run_name)
        rows = read_results(outputs["results_uri"])
        rows_by_model[key] = {note_of(row): row for row in rows}
        models[key] = {
            "run": run_name,
            "metrics": outputs["metrics"],
            "breakdown": breakdown(rows, meta),
        }
        if "training" in outputs:
            models[key]["training"] = outputs["training"]

    # Exemples : notes où le modèle de base se trompe, mises côte à côte
    examples = []
    for note, base_row in rows_by_model["base"].items():
        tuned_row = rows_by_model["finetuned"][note]
        if base_row["exact_match"] == "0" and len(note) < 420:
            examples.append(
                {
                    "notes": note,
                    "reference": tuned_row["reference"],
                    "base": base_row["extracted_response"],
                    "finetuned": tuned_row["extracted_response"],
                }
            )
    endpoint = json.loads(ENDPOINT_OUTPUTS_PATH.read_text(encoding="utf-8"))
    endpoint_tests = [item for item in endpoint if item["source"] == "test"]

    results = {
        "test_set_size": len(rows_by_model["finetuned"]),
        "models": models,
        "examples": examples[:3],
        "endpoint": {
            "notes": len(endpoint_tests),
            "exact": sum(item["exact_match"] for item in endpoint_tests),
            "latency_median_s": sorted(i["latency_seconds"] for i in endpoint_tests)[
                len(endpoint_tests) // 2
            ],
        },
    }
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"-> {OUTPUT_PATH}")
    for key, model in models.items():
        print(key, {k: round(v, 3) for k, v in model["metrics"].items()})


if __name__ == "__main__":
    main()
