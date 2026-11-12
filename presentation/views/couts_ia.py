from ui.common import nav_buttons, page_header, render_content

FILE = "views/couts_ia.py"

page_header(FILE, "Combien ça coûte, et qui garde la main.")

render_content("couts.md")
render_content("ia_responsable.md")

nav_buttons(FILE)
