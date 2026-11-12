"""Éléments communs aux pages : sommaire de l'exposé, en-têtes, navigation."""

import json
from html import escape

import streamlit as st
from crm import config

from ui.theme import CSS

# (fichier, titre court) dans l'ordre de l'exposé
PAGES: list[tuple[str, str]] = [
    ("views/accueil.py", "Brief"),
    ("views/demo.py", "Démo"),
    ("views/pipeline.py", "Pipeline"),
    ("views/resultats.py", "Résultats"),
    ("views/monitoring.py", "Monitoring"),
    ("views/problemes.py", "Problèmes"),
    ("views/couts_ia.py", "Coûts & IA responsable"),
]
_FILES = [file for file, _ in PAGES]


def inject_theme() -> None:
    st.html(f"<style>{CSS}</style>")


def page_header(current_file: str, headline: str, lede: str | None = None) -> None:
    """Position dans l'exposé + phrase-titre qui dit l'idée de la page."""
    index = _FILES.index(current_file)
    title = PAGES[index][1]
    lede_html = f'<p class="lede">{escape(lede)}</p>' if lede else ""
    st.html(
        f'<header class="page-head"><div class="eyebrow">{index + 1} / {len(PAGES)} · {escape(title)}</div>'
        f'<h1 class="headline">{escape(headline)}</h1>{lede_html}</header>'
    )


def section(title: str) -> None:
    st.html(f'<h2 class="section-title">{escape(title)}</h2>')


def render_content(name: str) -> None:
    """Affiche un texte de content/ (modifiable sans toucher au code)."""
    st.markdown((config.CONTENT_DIR / name).read_text(encoding="utf-8"))


def load_json(name: str):
    """Lit un fichier de data/, ou renvoie None s'il n'existe pas encore."""
    path = config.DATA_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def nav_buttons(current_file: str) -> None:
    """Page précédente / suivante, comme des slides."""
    index = _FILES.index(current_file)
    st.html('<div style="height:2.2rem"></div>')
    left, _, right = st.columns([2, 3, 2])
    if index > 0 and left.button(
        f"← {PAGES[index - 1][1]}", type="tertiary", key="nav_prev"
    ):
        st.switch_page(_FILES[index - 1])
    if index < len(_FILES) - 1:
        with right.container(horizontal=True, horizontal_alignment="right"):
            if st.button(f"{PAGES[index + 1][1]} →", type="tertiary", key="nav_next"):
                st.switch_page(_FILES[index + 1])
