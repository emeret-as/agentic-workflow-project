from html import escape

import streamlit as st
from crm import config
from crm.prompt import PROMPT_VERSION
from ui.common import nav_buttons, page_header

FILE = "views/pipeline.py"

page_header(
    FILE,
    "Le flux du cours, de la donnée au monitoring.",
    "Chaque étape tourne sur Google Cloud comme dans les TP ; les données, le prompt et les métriques sont les nôtres.",
)


def step(name: str, detail: str, css_class: str = "") -> str:
    class_attr = f' class="{css_class}"' if css_class else ""
    return f"<li{class_attr}><b>{name}</b><span>{detail}</span></li>"


st.html(
    '<div class="lanes">'
    '<section class="lane"><div class="label">Préparer</div><ol class="flowlist">'
    + step(
        "Gemini (Vertex AI)",
        "tire une fiche, puis rédige la note : 6 styles, 3 longueurs, un élément parasite",
    )
    + step(
        "Contrôle croisé",
        "une seconde extraction doit retrouver la fiche, sinon la note est écartée",
    )
    + step(
        "GCS", "558 notes gardées, versionnées dans le repo et copiées dans le bucket"
    )
    + '</ol></section><div class="lane-arrow"></div>'
    '<section class="lane lane--pipeline"><div class="label">Entraîner · pipeline Vertex AI</div><ol class="flowlist">'
    + step(
        "Transformation",
        f"format de conversation Phi-3, prompt {PROMPT_VERSION} ; 502 notes d'entraînement, 56 de test",
    )
    + step(
        "Fine-tuning",
        "LoRA r=8 sur Phi-3 chargé en 4 bits, 3 epochs, 1 h 23 sur un GPU T4",
    )
    + step(
        "Inférence",
        "le modèle fine-tuné, et Phi-3 de base dans un second pipeline, sur les 56 mêmes notes",
    )
    + step(
        "Évaluation",
        "JSON, schéma, fiche exacte, champ inventé, champ par champ → page Résultats",
    )
    + '</ol></section><div class="lane-arrow"></div>'
    '<section class="lane"><div class="label">Servir et suivre</div><ol class="flowlist">'
    + step("Model Registry", "emeret-crm-phi3, enregistré avec son handler")
    + step("Endpoint", "n1-standard-4 + T4, déployé pour la démo, supprimé juste après")
    + step("Apps", "Chainlit (TP) et Streamlit (cette présentation)", "is-app")
    + step("Langfuse", "auto-hébergé : traces, scores, juge LLM, dashboard")
    + "</ol></section></div>"
)

st.html(
    '<div class="facts">'
    "<span>modèle de base <b>Phi-3-mini-4k-instruct</b></span>"
    f"<span>modèle servi <b>{escape(config.MODEL_NAME)} v{escape(config.MODEL_VERSION)}</b></span>"
    f"<span>prompt <b>{PROMPT_VERSION}</b></span>"
    "<span>run <b>model-training-pipeline-20261112183827</b></span></div>"
)

nav_buttons(FILE)
