import streamlit as st
from crm import config
from crm.langfuse_stats import JUDGE_SCORE, fetch_stats
from ui.common import nav_buttons, page_header, render_content, section
from ui.components import empty_html

FILE = "views/monitoring.py"

# (score, ce qu'il mesure, qui le calcule) dans l'ordre d'affichage
SCORES = [
    ("json_valid", "the answer contains readable JSON", "code, every call"),
    ("schema_valid", "7 fields, right types, closed lists", "code, every call"),
    ("names_grounded", "company and contact appear in the notes", "code, every call"),
    (JUDGE_SCORE, "the record is faithful to the notes", "LLM judge (Gemini)"),
    ("exact_match", "all 7 fields equal the reference", "test notes only"),
    ("avis_utilisateur", "thumbs up from the salesperson", "salesperson, demo"),
    ("champs_corriges", "fields corrected before validation", "salesperson, demo"),
]

page_header(
    FILE,
    "Every record filled in leaves a trace.",
    "Langfuse records each call of the demo, its automatic scores, the LLM judge's verdict "
    "and the salesperson's feedback. The figures below are read live from Langfuse.",
)


@st.cache_data(ttl=20, show_spinner=False)
def stats():
    return fetch_stats()


try:
    data = stats() if config.LANGFUSE_ENABLED else None
except Exception:  # noqa: BLE001  Langfuse arrêté : la page reste lisible
    data = None

if data is None:
    st.html(
        empty_html(
            "Langfuse is not reachable: start it (<code>docker compose up -d</code> in the "
            "<code>langfuse</code> folder) to see live figures here."
        )
    )
else:
    p50, p95 = data["latency_p50"], data["latency_p95"]
    judge = data["judge"]
    st.html(
        '<div class="facts">'
        f"<span>traces <b>{data['traces']}</b></span>"
        + (f"<span>endpoint latency p50 <b>{p50:.1f} s</b></span>" if p50 else "")
        + (f"<span>p95 <b>{p95:.1f} s</b></span>" if p95 else "")
        + f"<span>LLM judge <b>{int(judge.get(1.0, 0))} faithful · "
        f"{int(judge.get(0.5, 0))} minor issue · {int(judge.get(0.0, 0))} unfaithful</b></span>"
        "</div>"
    )
    rows = []
    for name, meaning, source in SCORES:
        if name not in data["scores"]:
            continue
        mean, count = data["scores"][name]
        shown = f"{mean:.1f}" if name == "champs_corriges" else f"{mean * 100:.0f}%"
        rows.append(
            f"<tr><td><code>{name}</code></td><td>{meaning}</td><td>{source}</td>"
            f"<td class='num'>{shown}</td><td class='num'>{count}</td></tr>"
        )
    section("Scores in Langfuse")
    st.html(
        "<table class='table'><thead><tr><th>Score</th><th>What it measures</th><th>Computed by</th>"
        "<th class='num'>Average</th><th class='num'>Traces</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
    if st.button("Refresh", type="tertiary"):
        stats.clear()
        st.rerun()

if config.LANGFUSE_ENABLED:
    st.link_button("Open the Langfuse dashboard", config.LANGFUSE_DASHBOARD_URL)

render_content("monitoring.md")

nav_buttons(FILE)
