"""Point d'entrée : toute la présentation du projet, page par page.

Lancer depuis le dossier presentation/ (pour que .streamlit/config.toml soit lu) :
    cd presentation && uv run streamlit run app.py
"""

import sys
from pathlib import Path

# Racine du repo dans le chemin d'import : l'app réutilise src/crm_schema.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from ui.common import PAGES, inject_theme

st.set_page_config(page_title="Notes → fiche CRM", layout="wide")
inject_theme()

navigation = st.navigation(
    [
        st.Page(file, title=title, default=(i == 0))
        for i, (file, title) in enumerate(PAGES)
    ]
)
navigation.run()
