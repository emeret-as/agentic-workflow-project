from ui.common import nav_buttons, page_header, render_content

FILE = "views/problemes.py"

page_header(
    FILE,
    "What went wrong, and what we changed.",
    "Log kept since we picked the topic, updated at every step.",
)

render_content("problemes.md")

nav_buttons(FILE)
