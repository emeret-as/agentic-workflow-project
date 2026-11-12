import streamlit as st
from crm.guardrail import check_output
from ui.common import load_json, nav_buttons, page_header, section
from ui.components import highlighted_notes_html, label_html, record_card_html

FILE = "views/accueil.py"
HERO_EXAMPLE = "dictee"

page_header(
    FILE,
    "Des notes de rendez-vous à la fiche CRM, sans recopier.",
    "Un Phi-3-mini fine-tuné lit les notes brutes d'un commercial, en français, et remplit les "
    "sept champs de la fiche. Le commercial vérifie, corrige si besoin, et valide.",
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
            st.html(label_html("Ce que le commercial dicte"))
            st.html(highlighted_notes_html(notes, record))
        col_flow.html(
            '<div class="flow"><span>Phi-3<br>fine-tuné</span><div class="flow__arrow"></div></div>'
        )
        with col_record:
            st.html(label_html("Ce que le CRM reçoit"))
            st.html(record_card_html(record, notes))

section("Le besoin")
st.html(
    """
<div class="grid grid--3">
  <div class="block"><div class="label">Le problème</div>
    <p>Après chaque rendez-vous, le commercial recopie ses notes dans le CRM. C'est long, donc souvent
    bâclé : fiches incomplètes, relances oubliées, prévisions de vente faussées.</p></div>
  <div class="block"><div class="label">Pour qui</div>
    <p>Les commerciaux B2B, qui saisissent les fiches. Leurs managers, qui pilotent les ventes à partir
    de ces fiches.</p></div>
  <div class="block"><div class="label">Ce que fait l'outil</div>
    <p>Le commercial colle ses notes telles quelles : style télégraphique, e-mail, dictée, fautes
    comprises. Le modèle remplit la fiche ; rien n'est enregistré sans la validation du commercial.</p></div>
</div>
"""
)

section("La fiche, comme dans un vrai CRM")
st.html(
    """
<table class="table">
  <thead><tr><th>Champ</th><th>Ce que le modèle doit renvoyer</th></tr></thead>
  <tbody>
    <tr><td>Entreprise</td><td>le nom du client, toujours présent</td></tr>
    <tr><td>Interlocuteur, fonction</td><td>recopiés depuis les notes, sinon <code>null</code></td></tr>
    <tr><td>Besoin</td><td>une valeur d'une liste fermée de 8 (migration du CRM, cybersécurité, tableaux de bord…)</td></tr>
    <tr><td>Budget</td><td>un entier en euros (« 124 k€ » devient 124000), sinon <code>null</code></td></tr>
    <tr><td>Prochaine action</td><td>une valeur d'une liste fermée de 6 (proposition chiffrée, démo, rappel…)</td></tr>
    <tr><td>Échéance</td><td>une date AAAA-MM-JJ, seulement si c'est l'échéance du projet</td></tr>
  </tbody>
</table>
<p class="aside">Les listes fermées sont celles d'un CRM : une valeur hors liste ne pourrait pas être
enregistrée, donc le garde-fou la refuse.</p>
"""
)

section("Pourquoi un petit modèle fine-tuné")
st.html(
    """
<div class="grid grid--3">
  <div class="block"><div class="label">Confidentialité</div>
    <p>Les notes parlent de vrais clients. Le modèle tourne dans notre projet Google Cloud : rien ne part
    vers une API externe.</p></div>
  <div class="block"><div class="label">Coût</div>
    <p>Phi-3-mini, 3,8 milliards de paramètres, tient sur un seul GPU T4. L'entraînement LoRA ne
    touche que 12,6 millions de paramètres.</p></div>
  <div class="block"><div class="label">Format fiable</div>
    <p>Sans entraînement, Phi-3 ne connaît ni nos listes fermées ni notre format. Le fine-tuning les
    lui apprend : la page Résultats compare les deux modèles sur les mêmes notes.</p></div>
</div>
"""
)

section("Comment on saura que ça marche")
st.html(
    """
<table class="table">
  <thead><tr><th>Mesure</th><th>Ce qu'elle vérifie</th><th>Où on la mesure</th></tr></thead>
  <tbody>
    <tr><td>JSON valide, schéma valide</td><td>la réponse se lit, les 7 champs ont le bon type et les bonnes valeurs</td><td>pipeline, et à chaque appel</td></tr>
    <tr><td>Fiche exacte</td><td>les 7 champs égaux à la fiche de référence</td><td>pipeline (jeu de test)</td></tr>
    <tr><td>Champ inventé</td><td>une valeur donnée là où la référence dit « absent »</td><td>pipeline (jeu de test)</td></tr>
    <tr><td>Noms retrouvés</td><td>entreprise et contact présents dans les notes</td><td>Langfuse, à chaque appel</td></tr>
    <tr><td>Fidélité de la fiche</td><td>un juge LLM relit la note et la fiche</td><td>Langfuse, à chaque appel</td></tr>
    <tr><td>Champs corrigés</td><td>ce que le commercial change avant de valider</td><td>Langfuse, en production</td></tr>
  </tbody>
</table>
"""
)

section("Ce qui peut mal tourner")
st.html(
    """
<table class="table">
  <thead><tr><th>Risque</th><th>Parade</th></tr></thead>
  <tbody>
    <tr><td>Une date ou un chiffre parasite repris dans la fiche (séminaire, budget d'un concurrent)</td>
        <td>un élément parasite dans 4 notes sur 5 des données ; juge LLM ; validation humaine</td></tr>
    <tr><td>Un texte qui n'est pas une note : le modèle invente une fiche complète</td>
        <td>score « noms retrouvés » à 0 et alerte « à vérifier » sur chaque champ absent des notes</td></tr>
    <tr><td>Un besoin hors liste</td><td>le garde-fou bloque la fiche, rien n'est enregistré</td></tr>
    <tr><td>Données d'entraînement synthétiques</td><td>notes générées par Gemini, contrôlées par une seconde extraction ;
        test aussi sur des notes pièges écrites à la main</td></tr>
  </tbody>
</table>
<p class="aside"><b>Hors périmètre :</b> écriture directe dans Salesforce ou HubSpot, transcription audio
des appels, notes dans une autre langue que le français.</p>
"""
)

nav_buttons(FILE)
