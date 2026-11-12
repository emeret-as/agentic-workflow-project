"""Identité visuelle : papier blanc, encre bleu stylo, surligneur jaune.

Le sujet, ce sont des notes de commercial qui deviennent une fiche : les couleurs
et les polices viennent de ce monde (stylo, surligneur, formulaire), pas d'un
thème générique. Toutes les couleurs et polices sont définies ici, une seule fois.
"""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=IBM+Plex+Mono:wght@400;500&family=Public+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap');

:root {
  --paper: #FBFBF8;
  --paper-2: #F0F1EC;
  --ink: #1C2333;
  --ink-2: #545C70;
  --rule: #D8DBE2;
  --carbon: #2F45C5;
  --carbon-dark: #2337A8;
  --marker: #FFE45C;
  --alert: #C3352B;
  --display: 'Archivo', 'Helvetica Neue', Arial, sans-serif;
  --body: 'Public Sans', 'Helvetica Neue', Arial, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, Menlo, monospace;
}

/* ---- Base --------------------------------------------------------------- */
.stApp { background: var(--paper); color: var(--ink); }
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea,
.stApp button, .stApp td, .stApp th, .stApp dd, .stApp dt { font-family: var(--body); }
.stApp code, .stApp pre { font-family: var(--mono); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
[data-testid="stMainBlockContainer"] { max-width: 1180px; padding: 2.6rem 3.5rem 4rem; }
.stApp .stMarkdown p, .stApp .stMarkdown li { font-size: 1.08rem; line-height: 1.55; }
.stApp .stMarkdown code {
  background: #fff; border: 1px solid var(--rule); color: var(--ink);
  padding: .05em .35em; border-radius: 3px; font-size: .86em;
}
.stApp :focus-visible { outline: 2px solid var(--carbon); outline-offset: 2px; }

/* ---- Barre latérale : le sommaire de l'exposé ----------------------------- */
[data-testid="stSidebar"] { background: var(--paper-2); border-right: 1px solid var(--rule); }
[data-testid="stSidebarNav"] a span { font-family: var(--body); font-size: .98rem; color: var(--ink); }

/* ---- En-tête de page : position dans l'exposé + phrase-titre ------------- */
.page-head { margin: 0 0 2.2rem; }
.eyebrow {
  font-family: var(--mono); font-size: .78rem; font-weight: 500;
  letter-spacing: .1em; text-transform: uppercase; color: var(--carbon); margin: 0 0 .9rem;
}
.stApp h1.headline {
  font-family: var(--display); font-stretch: 118%; font-weight: 760;
  font-size: clamp(2.1rem, 4.1vw, 3.45rem); line-height: 1.05; letter-spacing: -.012em;
  color: var(--ink); max-width: 21ch; margin: 0; padding: 0;
}
.lede { font-size: 1.27rem; line-height: 1.5; color: var(--ink-2); max-width: 58ch; margin: 1.1rem 0 0; }

.stApp h2.section-title, .stApp .stMarkdown h2 {
  font-family: var(--display); font-stretch: 112%; font-weight: 680;
  font-size: 1.5rem; line-height: 1.2; color: var(--ink);
  border-top: 1.5px solid var(--ink); padding: .9rem 0 0; margin: 2.6rem 0 1rem;
}
.label {
  font-family: var(--mono); font-size: .74rem; font-weight: 500; letter-spacing: .09em;
  text-transform: uppercase; color: var(--ink-2); margin: 0 0 .5rem;
}

/* ---- Blocs de texte ------------------------------------------------------ */
.grid { display: grid; gap: 1.6rem 2.6rem; }
.grid--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.block .label { color: var(--carbon); }
.block p { font-size: 1.08rem; line-height: 1.52; margin: 0; color: var(--ink); }
.aside { font-size: 1rem; color: var(--ink-2); margin: 1.4rem 0 0; }
.aside b { color: var(--ink); font-weight: 600; }

/* ---- Tableaux ------------------------------------------------------------ */
.table, .stApp .stMarkdown table { width: 100%; border-collapse: collapse; font-size: 1rem; }
.table th, .stApp .stMarkdown th {
  font-family: var(--mono); font-size: .72rem; font-weight: 500; letter-spacing: .08em;
  text-transform: uppercase; color: var(--ink-2); text-align: left; background: transparent;
  border: none; border-bottom: 1.5px solid var(--ink); padding: .5rem 1rem .5rem 0;
}
.table td, .stApp .stMarkdown td {
  border: none; border-bottom: 1px solid var(--rule); background: transparent;
  padding: .75rem 1rem .75rem 0; vertical-align: top; line-height: 1.45;
}
.table td:first-child { font-weight: 600; }
.table .num { font-family: var(--mono); text-align: right; white-space: nowrap; }
.table .up { color: var(--carbon); }
.table .down { color: var(--alert); }

/* ---- Notes brutes et surligneur (la signature) ---------------------------- */
.notes {
  font-family: var(--mono); font-size: .95rem; line-height: 1.95; color: var(--ink);
  background: #fff; border: 1px solid var(--rule); border-radius: 3px;
  padding: 1rem 1.2rem; white-space: pre-wrap; overflow-wrap: anywhere;
}
mark.hl {
  color: inherit; padding: 0 .12em;
  background: linear-gradient(transparent 14%, var(--marker) 14%, var(--marker) 86%, transparent 86%) no-repeat;
  background-size: 100% 100%;
  -webkit-box-decoration-break: clone; box-decoration-break: clone;
  animation: marker-sweep .45s ease-out both; animation-delay: calc(var(--i, 0) * 160ms + 120ms);
}
.hl__tag {
  font-family: var(--mono); font-size: .62rem; font-weight: 500; letter-spacing: .06em;
  text-transform: uppercase; color: var(--carbon); vertical-align: super; margin: 0 .2em 0 .12em;
}
@keyframes marker-sweep { from { background-size: 0% 100%; } to { background-size: 100% 100%; } }

/* ---- Fiche CRM : un formulaire, avec son tampon ---------------------------- */
.record { background: #fff; border: 1.5px solid var(--ink); border-radius: 4px; padding: 1rem 1.3rem .9rem; }
.record__head {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  border-bottom: 1.5px solid var(--ink); padding-bottom: .7rem; margin-bottom: .2rem;
}
.record__title { font-family: var(--display); font-stretch: 118%; font-weight: 720; font-size: 1.3rem; }
.stamp {
  font-family: var(--mono); font-size: .72rem; font-weight: 500; letter-spacing: .14em;
  text-transform: uppercase; color: var(--carbon); border: 1.5px solid var(--carbon);
  border-radius: 3px; padding: .22rem .6rem; transform: rotate(-3deg); white-space: nowrap;
}
.stamp--validated { color: var(--ink); border-color: var(--ink); transform: rotate(2deg); }
.stamp--refused { color: var(--alert); border-color: var(--alert); }
.record dl { margin: 0; }
.field {
  display: grid; grid-template-columns: 9.5rem minmax(0, 1fr); gap: 1rem;
  padding: .72rem 0; border-bottom: 1px solid var(--rule);
}
.field:last-child { border-bottom: none; }
.field dt {
  font-family: var(--mono); font-size: .72rem; font-weight: 500; letter-spacing: .08em;
  text-transform: uppercase; color: var(--ink-2); padding-top: .3rem; align-self: start; justify-self: start;
}
.field dt.is-marked { background: linear-gradient(transparent 55%, var(--marker) 55%); }
.field dd { margin: 0; font-size: 1.14rem; line-height: 1.4; color: var(--ink); }
.field dd.is-empty { color: var(--ink-2); font-style: italic; }
.field__status { display: block; font-family: var(--mono); font-size: .72rem; color: var(--ink-2); margin-top: .25rem; }
.field__status--check { color: var(--alert); }
.record__checks {
  display: flex; flex-wrap: wrap; gap: .3rem 1.4rem; border-top: 1px solid var(--rule);
  margin-top: .3rem; padding-top: .7rem; font-family: var(--mono); font-size: .76rem; color: var(--ink-2);
}
.record__checks .is-bad { color: var(--alert); }
.refused__lead { font-size: 1.05rem; margin: .8rem 0 .4rem; }
.refused__errors { margin: 0 0 .4rem; padding-left: 1.1rem; font-family: var(--mono); font-size: .85rem; color: var(--alert); }

/* ---- Transformation notes → fiche (page d'accueil) ------------------------ */
.flow {
  display: flex; flex-direction: column; align-items: center; gap: .7rem; text-align: center;
  font-family: var(--mono); font-size: .7rem; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-2);
}
.flow__arrow { width: 100%; height: 1.5px; background: var(--ink); position: relative; }
.flow__arrow::after {
  content: ""; position: absolute; right: -1px; top: -5px;
  border-left: 9px solid var(--ink); border-top: 5.5px solid transparent; border-bottom: 5.5px solid transparent;
}

/* ---- États : vide, bandeau ---------------------------------------------- */
.empty {
  border: 1.5px dashed #B6BBC8; border-radius: 4px; padding: 1.3rem 1.4rem;
  color: var(--ink-2); font-size: 1.05rem; line-height: 1.5;
}
.banner {
  font-family: var(--mono); font-size: .8rem; line-height: 1.45; color: var(--ink);
  background: #fff; border-left: 3px solid var(--carbon); padding: .55rem .8rem; margin: 0 0 .9rem;
}
.banner--alert { border-left-color: var(--alert); }

/* ---- Pipeline : trois colonnes, une seule séquence numérotée ---------------- */
.lanes {
  display: grid; grid-template-columns: minmax(0, 1fr) 1.6rem minmax(0, 1.2fr) 1.6rem minmax(0, 1.2fr);
  gap: 0 .9rem; align-items: start; counter-reset: step; margin: .4rem 0 0;
}
.lane .label { margin-bottom: .7rem; }
.lane--pipeline { border: 1.5px dashed var(--carbon); border-radius: 4px; padding: .8rem .9rem .9rem; margin-top: -.9rem; }
.lane--pipeline .label { color: var(--carbon); }
.lane-arrow { align-self: center; height: 1.5px; background: var(--ink); position: relative; }
.lane-arrow::after {
  content: ""; position: absolute; right: -1px; top: -5px;
  border-left: 9px solid var(--ink); border-top: 5.5px solid transparent; border-bottom: 5.5px solid transparent;
}
.flowlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: .5rem; }
.flowlist li {
  counter-increment: step; display: grid; grid-template-columns: 1.5rem minmax(0, 1fr); row-gap: .15rem;
  background: #fff; border: 1.2px solid var(--ink); border-radius: 3px; padding: .6rem .75rem .65rem;
}
.flowlist li::before { content: counter(step); grid-row: span 2; font-family: var(--mono); font-size: .82rem; color: var(--carbon); padding-top: .12rem; }
.flowlist b { font-weight: 600; font-size: 1.02rem; }
.flowlist span { font-size: .9rem; line-height: 1.35; color: var(--ink-2); }
.flowlist li.is-app { border: 2px solid var(--carbon); }
.facts { display: flex; flex-wrap: wrap; gap: .4rem 2.4rem; margin: 1rem 0 0; font-family: var(--mono); font-size: .85rem; color: var(--ink-2); }
.facts b { color: var(--ink); font-weight: 500; }
.facts--stack { flex-direction: column; gap: .35rem; font-size: .8rem; }

/* ---- Widgets ------------------------------------------------------------- */
.stApp textarea { font-family: var(--mono); font-size: .95rem; line-height: 1.6; }
[data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input { background: #fff; }
.stApp [data-testid="stWidgetLabel"] p {
  font-family: var(--mono); font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-2);
}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--carbon); border: 1.5px solid var(--carbon); border-radius: 3px; font-weight: 600;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: var(--carbon-dark); border-color: var(--carbon-dark);
}
[data-testid="stBaseButton-secondary"] { border-radius: 3px; border: 1.5px solid var(--ink); background: transparent; font-weight: 600; }
[data-testid="stBaseButton-tertiary"] p { font-family: var(--mono); font-size: .85rem; color: var(--carbon); }
[data-testid="stExpander"] details { border-radius: 3px; border-color: var(--rule); background: #fff; }

/* ---- Petits écrans, mouvement réduit --------------------------------------- */
@media (max-width: 860px) {
  [data-testid="stMainBlockContainer"] { padding: 3.4rem 1rem 3rem; }
  .flow__arrow { width: 1.5px; height: 2.2rem; }
  .flow__arrow::after {
    right: -5px; top: auto; bottom: -1px; border-top: 9px solid var(--ink);
    border-left: 5.5px solid transparent; border-right: 5.5px solid transparent; border-bottom: none;
  }
  .grid--3, .lanes { grid-template-columns: 1fr; }
  .lane-arrow { display: none; }
  .lane { margin-bottom: 1.2rem; }
  .field { grid-template-columns: 1fr; gap: .15rem; }
}
@media (prefers-reduced-motion: reduce) { mark.hl { animation: none; } }
"""
