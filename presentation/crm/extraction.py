"""Extraction d'une fiche : appel du modèle + garde-fou + traçage Langfuse.

Deux sources possibles :
- « endpoint » : le vrai modèle sur Vertex AI, chaque appel est tracé dans Langfuse ;
- « rejeu »    : une réponse enregistrée à l'avance (data/replay.json), en secours
                 si l'endpoint ne répond pas. Rien n'est envoyé à Langfuse.

Les traces ont la même forme que celles de l'app Chainlit (span « User Message »,
generation « Vertex AI endpoint », scores json_valid / schema_valid /
names_grounded) : le dashboard et le juge LLM de Langfuse s'appliquent aux deux.
"""

import json
import time
from dataclasses import dataclass

from crm import config
from crm.client import EndpointError, call_endpoint, generation_parameters
from crm.guardrail import GuardrailResult, check_output
from crm.prompt import PROMPT_VERSION, build_prompt, extract_answer
from src.crm_schema import normalize
from src.llm_judge import SCORE_NAME, judge

REPLAY_FILE = config.DATA_DIR / "replay.json"


@dataclass
class ExtractionResult:
    source: str  # "endpoint", "rejeu-enregistre" ou "rejeu-fictif"
    answer: str
    check: GuardrailResult
    latency_s: float | None
    trace_id: str | None = None
    verdict: tuple[float, str] | None = None  # juge LLM : (score, justification)


def names_grounded(record: dict | None, notes: str) -> bool:
    """Entreprise et contact se retrouvent dans les notes (même règle que l'app Chainlit)."""
    if record is None:
        return False
    text = normalize(notes)
    names = [record.get("company"), record.get("contact_name")]
    return all(name is None or normalize(name) in text for name in names)


def _check_and_score(
    langfuse, notes: str, answer: str
) -> tuple[GuardrailResult, str | None]:
    """Garde-fou + scores sur la trace en cours."""
    check = check_output(answer)
    trace_id = None
    if langfuse is not None:
        langfuse.update_current_span(output=answer)
        trace_id = langfuse.get_current_trace_id()
        scores = {
            "json_valid": check.json_valid,
            "schema_valid": check.schema_valid,
            "names_grounded": check.schema_valid
            and names_grounded(check.record, notes),
        }
        for name, ok in scores.items():
            langfuse.score_current_span(name=name, value=float(ok), data_type="NUMERIC")
    return check, trace_id


def _extract_untraced(notes: str) -> tuple[str, GuardrailResult, str | None]:
    answer = extract_answer(call_endpoint(build_prompt(notes)))
    check, _ = _check_and_score(None, notes, answer)
    return answer, check, None, None


def _extract_traced(notes: str) -> tuple[str, GuardrailResult, str | None]:
    from langfuse import get_client, observe

    langfuse = get_client()

    @observe(name="User Message")
    def run(notes: str):
        langfuse.update_current_trace(
            tags=["streamlit"], metadata={"prompt_version": PROMPT_VERSION}
        )
        langfuse.update_current_span(input=notes)
        prompt = build_prompt(notes)
        with langfuse.start_as_current_generation(
            name="Vertex AI endpoint",
            model=config.MODEL_NAME,
            input={
                "instances": [{"input": prompt}],
                "parameters": generation_parameters(),
            },
            model_parameters=generation_parameters(),
            version=config.MODEL_VERSION,
            metadata={"prompt_version": PROMPT_VERSION},
        ) as generation:
            try:
                started = time.perf_counter()
                answer = extract_answer(call_endpoint(prompt))
                model_latency = time.perf_counter() - started
            except EndpointError as error:
                generation.update(level="ERROR", status_message=str(error))
                raise
            generation.update(output=answer)
        check, trace_id = _check_and_score(langfuse, notes, answer)
        verdict = None
        if (
            check.record is not None
        ):  # une fiche refusée par le garde-fou n'est pas jugée
            try:
                verdict = judge(notes, answer)
                langfuse.score_current_span(
                    name=SCORE_NAME,
                    value=verdict[0],
                    data_type="NUMERIC",
                    comment=verdict[1],
                )
            except Exception:  # noqa: BLE001  juge indisponible : la démo continue
                verdict = None
        return answer, check, trace_id, verdict, model_latency

    try:
        return run(notes)
    finally:
        langfuse.flush()


def extract_live(notes: str) -> ExtractionResult:
    """Appelle le vrai modèle. Lève EndpointError avec un message lisible si ça échoue."""
    if config.LANGFUSE_ENABLED:
        answer, check, trace_id, verdict, latency = _extract_traced(notes)
        return ExtractionResult("endpoint", answer, check, latency, trace_id, verdict)
    start = time.perf_counter()
    answer, check, trace_id, verdict = _extract_untraced(notes)
    return ExtractionResult("endpoint", answer, check, time.perf_counter() - start)


def load_replay() -> dict:
    if not REPLAY_FILE.exists():
        return {}
    return json.loads(REPLAY_FILE.read_text(encoding="utf-8"))


def extract_replay(example_id: str | None) -> ExtractionResult | None:
    """Renvoie la réponse enregistrée pour un exemple, ou None s'il n'y en a pas."""
    entry = load_replay().get(example_id or "")
    if entry is None:
        return None
    source = (
        "rejeu-enregistre" if entry.get("source") == "enregistree" else "rejeu-fictif"
    )
    answer = entry["output"]
    return ExtractionResult(
        source, answer, check_output(answer), entry.get("latency_s")
    )
