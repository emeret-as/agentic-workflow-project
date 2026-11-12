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
    ("valid_json_mean", "JSON valide", True),
    ("valid_schema_mean", "Schéma valide (types, listes fermées)", True),
    ("exact_match_mean", "Fiche exacte (7 champs justes)", True),
    ("field_accuracy_mean", "Champs justes", True),
    ("hallucinated_field_mean", "Fiches avec un champ inventé", False),
]
DISTRACTORS = {
    "none": "aucun",
    "date": "une autre date (séminaire, congés…)",
    "figure": "un autre chiffre (effectif, chiffre d'affaires…)",
    "competitor": "un concurrent et son budget",
    "colleague": "un collègue du contact",
}
STYLES = {
    "prose": "prose",
    "email": "e-mail",
    "dictated": "dictée",
    "telegraphic": "télégraphique",
    "bullets": "liste à puces",
    "crm_comment": "commentaire CRM",
}

page_header(
    FILE,
    "Ce que le fine-tuning change, mesuré sur le même jeu de test.",
    "Phi-3 de base et Phi-3 fine-tuné reçoivent les mêmes 56 notes, avec le même prompt, "
    "et sont notés par le même composant d'évaluation du pipeline.",
)


def pct(value: float) -> str:
    return f"{value * 100:.0f} %".replace(".", ",")


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
        "<table class='table'><thead><tr><th>Mesure</th><th class='num'>Phi-3 de base</th>"
        "<th class='num'>Phi-3 fine-tuné</th><th class='num'>Écart</th></tr></thead>"
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
        "<table class='table'><thead><tr><th>Notes</th><th class='num'>Nombre</th>"
        "<th class='num'>Fiches exactes, base</th><th class='num'>Fiches exactes, fine-tuné</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


results = load_json("results.json")
if results is None:
    st.html(
        empty_html(
            "Pas encore de chiffres : lancer <code>scripts/build_results.py</code> une fois les deux "
            "pipelines terminés, il écrit <code>presentation/data/results.json</code>."
        )
    )
else:
    tuned_model = results["models"]["finetuned"]
    base_model = results["models"].get("base")
    tuned, base = tuned_model["metrics"], (base_model or {}).get("metrics", {})
    st.html(
        f"<p class='aside'>Jeu de test : <b>{results['test_set_size']} notes</b> jamais vues à "
        "l'entraînement, tirées au hasard dans les données.</p>"
        + comparison_table(base, tuned)
    )

    section("Champ par champ")
    per_field = pd.DataFrame(
        {
            "Phi-3 de base": {
                label: base.get(f"field_{key}_mean", 0) for key, label in FIELDS
            },
            "Phi-3 fine-tuné": {
                label: tuned.get(f"field_{key}_mean", 0) for key, label in FIELDS
            },
        }
    )
    st.bar_chart(
        per_field, stack=False, horizontal=True, color=[BASE_COLOR, TUNED_COLOR]
    )

    section("Les notes piégées")
    st.html(
        "<p>Quatre notes sur cinq contiennent un élément parasite, que la fiche ne doit pas reprendre.</p>"
        + breakdown_table(base_model, tuned_model, "distractor", DISTRACTORS)
    )
    endpoint = results.get("endpoint")
    if endpoint:
        st.html(
            "<p class='aside'>La seule erreur du modèle fine-tuné est une date de séminaire prise pour "
            "l'échéance. Sur l'endpoint, où Phi-3 tourne en float16 au lieu de 4 bits, les mêmes notes "
            f"donnent <b>{endpoint['exact']}/{endpoint['notes']} fiches exactes</b>, en "
            f"{str(endpoint['latency_median_s']).replace('.', ',')} s par note (médiane).</p>"
        )
    with st.expander("Par style de note"):
        st.html(breakdown_table(base_model, tuned_model, "style", STYLES))

    if results.get("examples"):
        section("Même note, deux modèles")
        for example in results["examples"][:2]:
            st.html(f'<div class="notes">{escape(example["notes"])}</div>')
            col_base, col_tuned = st.columns(2)
            with col_base:
                st.html(label_html("Phi-3 de base"))
                st.code(
                    example["base"] or "(réponse vide)",
                    language="json",
                    wrap_lines=True,
                )
            with col_tuned:
                st.html(label_html("Phi-3 fine-tuné"))
                st.code(example["finetuned"], language="json", wrap_lines=True)

    training = tuned_model.get("training")
    if training:
        section("Entraînement")
        st.html(
            '<div class="facts">'
            f"<span>epochs <b>{training['num_train_epochs']:.0f}</b></span>"
            f"<span>LoRA <b>r={training['lora_r']:.0f}, α={training['lora_alpha']:.0f}</b></span>"
            f"<span>paramètres entraînés <b>{training['trainable_params'] / 1e6:.1f} M</b></span>"
            f"<span>perte entraînement <b>{training['train_loss']:.2f}</b></span>"
            f"<span>perte validation <b>{training['eval_loss']:.2f}</b></span></div>"
        )

nav_buttons(FILE)
