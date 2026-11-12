from ui.common import nav_buttons, page_header, render_content

FILE = "views/problemes.py"

page_header(
    FILE,
    "Ce qui a coincé, et ce qu'on a changé.",
    "Journal tenu depuis le choix du sujet, complété à chaque étape.",
)

render_content("problemes.md")

nav_buttons(FILE)
