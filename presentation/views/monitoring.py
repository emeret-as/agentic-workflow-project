import streamlit as st
from crm import config
from ui.common import nav_buttons, page_header, render_content
from ui.components import empty_html

FILE = "views/monitoring.py"

page_header(
    FILE,
    "Chaque fiche remplie laisse une trace.",
    "Langfuse enregistre chaque appel de la démo, ses scores automatiques et l'avis du commercial.",
)

screenshot = config.DATA_DIR / "langfuse_dashboard.png"
if screenshot.exists():
    st.image(str(screenshot), caption="Tableau de bord Langfuse", width="stretch")
else:
    st.html(
        empty_html(
            "La capture du tableau de bord Langfuse s'affichera ici : enregistrez-la sous "
            "<code>data/langfuse_dashboard.png</code>."
        )
    )
if config.LANGFUSE_ENABLED:
    st.link_button("Ouvrir Langfuse", config.LANGFUSE_DASHBOARD_URL)

render_content("monitoring.md")

nav_buttons(FILE)
