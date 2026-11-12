"""Démo live : notes → fiche CRM, garde-fou, validation humaine, retours vers Langfuse."""

import uuid
from html import escape

import streamlit as st
from crm import config
from crm.client import EndpointError
from crm.extraction import extract_live, extract_replay
from crm.feedback import send_thumbs, send_validation
from crm.prompt import PROMPT_VERSION
from crm.schema import FIELDS, NEED_LABELS, NEXT_ACTION_LABELS
from ui.common import load_json, nav_buttons, page_header
from ui.components import (
    banner_html,
    empty_html,
    highlighted_notes_html,
    label_html,
    record_card_html,
    refused_card_html,
)

FILE = "views/demo.py"
MODE_LIVE, MODE_REPLAY = "Modèle en ligne", "Rejeu enregistré"

examples = load_json("examples.json") or []
state = st.session_state
state.setdefault("notes", "")
state.setdefault("demo_result", None)


def use_example() -> None:
    """Choisir un exemple remplace le texte des notes."""
    title = state.get("example_pick")
    if title:
        state.notes = next(e["notes"] for e in examples if e["title"] == title)


CHOICES = {"need": NEED_LABELS, "next_action": NEXT_ACTION_LABELS}


def validation_input(key: str, label: str, value):
    """Champ du formulaire de validation : liste pour les catégories, texte sinon."""
    if key in CHOICES:
        options = list(CHOICES[key])
        return st.selectbox(
            label,
            options,
            index=options.index(value) if value in options else None,
            format_func=CHOICES[key].get,
            placeholder="non mentionné",
        )
    help_text = {
        "budget_eur": "En euros, sans espace : 124000",
        "deadline": "Format AAAA-MM-JJ",
    }.get(key)
    return st.text_input(
        label,
        value="" if value is None else str(value),
        placeholder="non mentionné",
        help=help_text,
    )


def clean_value(key: str, value):
    """Valeur saisie → valeur de la fiche (None si vide, entier pour le budget)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if key == "budget_eur":
        digits = "".join(char for char in str(value) if char.isdigit())
        return int(digits) if digits else None
    return value.strip() if isinstance(value, str) else value


def matching_example_id() -> str | None:
    """Le rejeu ne marche que si le texte est exactement celui d'un exemple."""
    return next(
        (e["id"] for e in examples if e["notes"].strip() == state.notes.strip()), None
    )


# -- Barre latérale : réglages de la démo --------------------------------------------
with st.sidebar:
    st.html('<div style="height:.6rem"></div>' + label_html("Réglages de la démo"))
    mode = st.radio(
        "Source des réponses",
        [MODE_LIVE, MODE_REPLAY],
        key="demo_mode",
        help="Le rejeu affiche des réponses enregistrées à l'avance, en secours si l'endpoint ne répond pas.",
    )
    endpoint_state = "configuré" if config.endpoint_configured() else "non configuré"
    langfuse_state = (
        "activé" if config.LANGFUSE_ENABLED else "désactivé (clés absentes)"
    )
    st.html(
        '<div class="facts facts--stack">'
        f"<span>modèle <b>{escape(config.MODEL_NAME)}</b></span>"
        f"<span>version <b>{escape(config.MODEL_VERSION)}</b></span>"
        f"<span>prompt <b>{PROMPT_VERSION}</b></span>"
        f"<span>endpoint <b>{endpoint_state}</b></span>"
        f"<span>langfuse <b>{langfuse_state}</b></span></div>"
    )
    if st.button(
        "Réveiller l'endpoint",
        help="À faire juste avant la démo : un premier appel pour vérifier qu'il répond.",
    ):
        try:
            with st.spinner("Appel de l'endpoint…"):
                warmup = extract_live(
                    examples[0]["notes"] if examples else "Test note."
                )
            st.success(f"L'endpoint répond ({warmup.latency_s:.1f} s).")
        except EndpointError as error:
            st.error(str(error))

page_header(FILE, "Collez des notes. Le modèle remplit la fiche.")

left, right = st.columns(2, gap="large")
current = state.demo_result

# -- Gauche : les notes ---------------------------------------------------------------
with left:
    st.html(label_html("Notes du rendez-vous"))
    if examples:
        st.pills(
            "Exemples",
            [e["title"] for e in examples],
            key="example_pick",
            on_change=use_example,
            label_visibility="collapsed",
        )
    st.text_area(
        "Notes du rendez-vous",
        key="notes",
        height=200,
        label_visibility="collapsed",
        placeholder="Collez ici les notes brutes, en français, telles que le commercial les a tapées ou dictées.",
    )
    if st.button(
        "Remplir la fiche",
        type="primary",
        disabled=not state.notes.strip(),
        width="stretch",
    ):
        result = None
        if mode == MODE_REPLAY:
            result = extract_replay(matching_example_id())
            if result is None:
                st.html(
                    banner_html(
                        "Pas de réponse enregistrée pour ce texte : le rejeu ne marche qu'avec les exemples.",
                        alert=True,
                    )
                )
        else:
            try:
                with st.spinner("Le modèle remplit la fiche… (5 à 15 s sur GPU T4)"):
                    result = extract_live(state.notes)
            except EndpointError as error:
                st.html(
                    banner_html(
                        f"{error} En secours : passer la source sur « {MODE_REPLAY} » dans la barre latérale.",
                        alert=True,
                    )
                )
        if result is not None:
            current = state.demo_result = {
                "id": uuid.uuid4().hex,
                "result": result,
                "notes": state.notes,
                "thumbs_sent": False,
                "validation": None,
            }

    if current is not None and current["result"].check.record is not None:
        st.html(
            '<div style="height:.8rem"></div>' + label_html("D'où vient chaque champ")
        )
        st.html(
            highlighted_notes_html(current["notes"], current["result"].check.record)
        )

# -- Droite : la fiche ------------------------------------------------------------------
with right:
    st.html(label_html("Fiche CRM"))
    if current is None:
        st.html(
            empty_html(
                "La fiche apparaîtra ici. Choisissez un exemple ou collez des notes, "
                "puis cliquez sur <b>Remplir la fiche</b>."
            )
        )
    else:
        result = current["result"]
        if result.source == "rejeu-fictif":
            st.html(
                banner_html(
                    "Rejeu · réponse fictive écrite à la main, en attendant une vraie réponse enregistrée du modèle.",
                    alert=True,
                )
            )
        elif result.source == "rejeu-enregistre":
            st.html(banner_html("Rejeu · réponse du modèle enregistrée à l'avance."))

        checks = [
            (
                "json valide" if result.check.json_valid else "json invalide",
                result.check.json_valid,
            ),
            (
                "schéma conforme"
                if result.check.schema_valid
                else "schéma non conforme",
                result.check.schema_valid,
            ),
        ]
        if result.latency_s is not None:
            checks.append((f"{result.latency_s:.1f} s".replace(".", ","), True))

        record = result.check.record
        if record is None:
            st.html(refused_card_html(result.check.errors, checks))
        else:
            stamp = "validated" if current["validation"] is not None else "draft"
            st.html(
                record_card_html(record, current["notes"], stamp=stamp, checks=checks)
            )
        with st.expander("Réponse brute du modèle"):
            st.code(result.answer or "(vide)", language="json")

        # -- Validation par le commercial : la vérité terrain envoyée à Langfuse -------
        if record is not None:
            st.html(
                '<div style="height:.6rem"></div>'
                + label_html("Validation par le commercial")
            )
            if result.trace_id is None:
                st.caption(
                    "Rejeu ou Langfuse désactivé : l'avis et la validation ne sont pas envoyés à Langfuse."
                )
            thumbs = st.feedback("thumbs", key=f"thumbs_{current['id']}")
            if thumbs is not None and not current["thumbs_sent"]:
                try:
                    send_thumbs(result.trace_id, thumbs == 1)
                    current["thumbs_sent"] = True
                except Exception as error:  # noqa: BLE001  Langfuse arrêté : la démo continue
                    st.html(
                        banner_html(f"Avis non envoyé à Langfuse : {error}", alert=True)
                    )

            with st.form(key=f"validation_{current['id']}", border=False):
                edited = {
                    key: validation_input(key, label, record.get(key))
                    for key, label in FIELDS
                }
                submitted = st.form_submit_button(
                    "Valider la fiche", type="primary", width="stretch"
                )
            if submitted and current["validation"] is None:
                corrected = {
                    key: clean_value(key, value) for key, value in edited.items()
                }
                try:
                    current["validation"] = send_validation(
                        result.trace_id, record, corrected
                    )
                    st.rerun()  # pour que le tampon passe à « Validée »
                except Exception as error:  # noqa: BLE001  Langfuse arrêté : la démo continue
                    st.html(
                        banner_html(
                            f"Validation non envoyée à Langfuse : {error}", alert=True
                        )
                    )
            if current["validation"] is not None:
                sent = (
                    " · envoyée dans Langfuse comme bonne réponse"
                    if result.trace_id
                    else ""
                )
                st.html(
                    banner_html(
                        f"Fiche validée · {current['validation']} champ(s) corrigé(s){sent}"
                    )
                )

nav_buttons(FILE)
