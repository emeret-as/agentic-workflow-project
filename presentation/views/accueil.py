import streamlit as st
from crm.guardrail import check_output
from ui.common import load_json, nav_buttons, page_header, section
from ui.components import highlighted_notes_html, label_html, record_card_html

FILE = "views/accueil.py"
HERO_EXAMPLE = "dictee"

page_header(
    FILE,
    "From meeting notes to a CRM record, without retyping.",
    "A fine-tuned Phi-3-mini reads a salesperson's raw notes (written in French) and fills in "
    "the seven fields of the record. The salesperson checks it, fixes it if needed, and validates.",
)

# La transformation, sur une vraie réponse du modèle : c'est le produit en une image.
examples = {e["id"]: e for e in load_json("examples.json") or []}
replay = load_json("replay.json") or {}
if HERO_EXAMPLE in examples and HERO_EXAMPLE in replay:
    notes = examples[HERO_EXAMPLE]["notes"]
    record = check_output(replay[HERO_EXAMPLE]["output"]).record
    if record:
        col_notes, col_flow, col_record = st.columns(
            [10, 2, 10], vertical_alignment="center"
        )
        with col_notes:
            st.html(label_html("What the salesperson dictates"))
            st.html(highlighted_notes_html(notes, record))
        col_flow.html(
            '<div class="flow"><span>Fine-tuned<br>Phi-3</span><div class="flow__arrow"></div></div>'
        )
        with col_record:
            st.html(label_html("What the CRM receives"))
            st.html(record_card_html(record, notes))

section("The record, as in a real CRM")
st.html(
    """
<table class="table">
  <thead><tr><th>Field</th><th>What the model must return</th></tr></thead>
  <tbody>
    <tr><td>Company</td><td>the client's name, always present</td></tr>
    <tr><td>Contact, role</td><td>copied from the notes, otherwise <code>null</code></td></tr>
    <tr><td>Need</td><td>one value from a closed list of 8 (CRM migration, cybersecurity, dashboards…)</td></tr>
    <tr><td>Budget</td><td>an integer in euros (« 124 k€ » becomes 124000), otherwise <code>null</code></td></tr>
    <tr><td>Next action</td><td>one value from a closed list of 6 (priced proposal, demo, follow-up call…)</td></tr>
    <tr><td>Deadline</td><td>a YYYY-MM-DD date, only if it is the project's deadline</td></tr>
  </tbody>
</table>
<p class="aside">The closed lists are those of a CRM: a value outside the list could not be saved,
so the guardrail rejects it.</p>
"""
)

nav_buttons(FILE)
