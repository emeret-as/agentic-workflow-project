"""Résultats : Phi-3 de base contre Phi-3 fine-tuné, sur le même jeu de test.

Lit data/results.json, produit par scripts/build_results.py à partir des deux
pipelines Vertex AI (même composant d'évaluation pour les deux modèles).
"""

from html import escape

import pandas as pd
import streamlit as st
from crm.schema import FIELDS
from ui.common import load_json, nav_buttons, page_header, section
from ui.components import empty_html, label_html

FILE = "views/resultats.py"
BASE_COLOR, TUNED_COLOR = "#A7AFC2", "#2F45C5"

# (clé de la métrique, libellé, plus haut = mieux ?)
SUMMARY = [
    ("valid_json_mean", "Valid JSON", True),
    ("valid_schema_mean", "Valid schema (types, closed lists)", True),
    ("exact_match_mean", "Exact record (all 7 fields right)", True),
    ("field_accuracy_mean", "Correct fields", True),
    ("hallucinated_field_mean", "Records with an invented field", False),
]
DISTRACTORS = {
    "none": "none",
    "date": "another date (seminar, holidays…)",
    "figure": "another figure (headcount, revenue…)",
    "competitor": "a competitor and its budget",
    "colleague": "a colleague of the contact",
}
STYLES = {
    "prose": "prose",
    "email": "e-mail",
    "dictated": "dictated",
    "telegraphic": "telegraphic",
    "bullets": "bullet list",
    "crm_comment": "CRM comment",
}

page_header(
    FILE,
    "What fine-tuning changes, measured on the same test set.",
    "Base Phi-3 and fine-tuned Phi-3 get the same 56 notes, with the same prompt, "
    "and are scored by the same pipeline evaluation component.",
)


def compact(text: str) -> str:
    """Retire les lignes vides d'une sortie de modèle (le modèle de base en met beaucoup)."""
    return "\n".join(line for line in text.splitlines() if line.strip())


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def comparison_table(base: dict, tuned: dict) -> str:
    rows = []
    for key, label, higher_is_better in SUMMARY:
        b, t = base.get(key), tuned.get(key)
        if b is None or t is None:
            continue
        delta = (t - b) * 100
        good = delta >= 0 if higher_is_better else delta <= 0
        rows.append(
            f"<tr><td>{label}</td><td class='num'>{pct(b)}</td><td class='num'>{pct(t)}</td>"
            f"<td class='num {'up' if good else 'down'}'>{delta:+.0f} pts</td></tr>"
        )
    return (
        "<table class='table'><thead><tr><th>Metric</th><th class='num'>Base Phi-3</th>"
        "<th class='num'>Fine-tuned Phi-3</th><th class='num'>Gap</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def breakdown_table(base: dict, tuned: dict, column: str, labels: dict) -> str:
    rows = []
    for value, label in labels.items():
        t = tuned["breakdown"][column].get(value)
        b = base["breakdown"][column].get(value) if base else None
        if t is None:
            continue
        base_cell = f"{b['exact']}/{b['n']}" if b else "–"
        rows.append(
            f"<tr><td>{escape(label)}</td><td class='num'>{t['n']}</td>"
            f"<td class='num'>{base_cell}</td><td class='num'>{t['exact']}/{t['n']}</td></tr>"
        )
    return (
        "<table class='table'><thead><tr><th>Notes</th><th class='num'>Count</th>"
        "<th class='num'>Exact records, base</th><th class='num'>Exact records, fine-tuned</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


results = load_json("results.json")
if results is None:
    st.html(
        empty_html(
            "No figures yet: run <code>scripts/build_results.py</code> once both pipelines are "
            "done, it writes <code>presentation/data/results.json</code>."
        )
    )
else:
    tuned_model = results["models"]["finetuned"]
    base_model = results["models"].get("base")
    tuned, base = tuned_model["metrics"], (base_model or {}).get("metrics", {})
    st.html(
        f"<p class='aside'>Test set: <b>{results['test_set_size']} notes</b> never seen in "
        "training, drawn at random from the data.</p>" + comparison_table(base, tuned)
    )

    section("Field by field")
    per_field = pd.DataFrame(
        {
            "Base Phi-3": {
                label: base.get(f"field_{key}_mean", 0) for key, label in FIELDS
            },
            "Fine-tuned Phi-3": {
                label: tuned.get(f"field_{key}_mean", 0) for key, label in FIELDS
            },
        }
    )
    st.bar_chart(
        per_field, stack=False, horizontal=True, color=[BASE_COLOR, TUNED_COLOR]
    )
    st.html(
        "<p class='aside'><b>Read with care.</b> The prompt does not list the closed-list values: "
        "base Phi-3 cannot guess <code>crm_migration</code> or <code>send_proposal</code>, hence its "
        "0% on need and next action. On the fields copied from the notes (company, contact, budget), "
        "the gap is 12 to 20 points. The real weakness of the base model lies elsewhere: the deadline "
        "(34% right) and invented fields, in 27% of its records.</p>"
    )

    section("Notes with a distractor")
    st.html(
        "<p>Four notes out of five contain a distractor that the record must not pick up.</p>"
        + breakdown_table(base_model, tuned_model, "distractor", DISTRACTORS)
    )
    endpoint = results.get("endpoint")
    if endpoint:
        st.html(
            "<p class='aside'>The only mistake of the fine-tuned model is a seminar date taken as "
            "the deadline. On the endpoint, where Phi-3 runs in float16 instead of 4 bits, the same "
            f"notes give <b>{endpoint['exact']}/{endpoint['notes']} exact records</b>, in "
            f"{endpoint['latency_median_s']} s per note (median).</p>"
        )
    with st.expander("By note style"):
        st.html(breakdown_table(base_model, tuned_model, "style", STYLES))

    if results.get("examples"):
        section("Same note, two models")
        for example in results["examples"][:2]:
            st.html(f'<div class="notes">{escape(example["notes"])}</div>')
            col_base, col_tuned = st.columns(2)
            with col_base:
                st.html(label_html("Base Phi-3"))
                st.code(
                    compact(example["base"]) or "(empty answer)",
                    language="json",
                    wrap_lines=True,
                )
            with col_tuned:
                st.html(label_html("Fine-tuned Phi-3"))
                st.code(example["finetuned"], language="json", wrap_lines=True)

    training = tuned_model.get("training")
    if training:
        section("Training")
        st.html(
            '<div class="facts">'
            f"<span>epochs <b>{training['num_train_epochs']:.0f}</b></span>"
            f"<span>LoRA <b>r={training['lora_r']:.0f}, α={training['lora_alpha']:.0f}</b></span>"
            f"<span>trained parameters <b>{training['trainable_params'] / 1e6:.1f} M</b></span>"
            f"<span>train loss <b>{training['train_loss']:.2f}</b></span>"
            f"<span>validation loss <b>{training['eval_loss']:.2f}</b></span></div>"
        )

nav_buttons(FILE)
