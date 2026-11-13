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
MODE_LIVE, MODE_REPLAY = "Live model", "Recorded replay"

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
            placeholder="not mentioned",
        )
    help_text = {
        "budget_eur": "In euros, no spaces: 124000",
        "deadline": "Format YYYY-MM-DD",
    }.get(key)
    return st.text_input(
        label,
        value="" if value is None else str(value),
        placeholder="not mentioned",
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
    st.html('<div style="height:.6rem"></div>' + label_html("Demo settings"))
    mode = st.radio(
        "Answer source",
        [MODE_LIVE, MODE_REPLAY],
        key="demo_mode",
        help="Replay shows answers recorded in advance, as a fallback if the endpoint does not answer.",
    )
    endpoint_state = "configured" if config.endpoint_configured() else "not configured"
    langfuse_state = "on" if config.LANGFUSE_ENABLED else "off (no keys)"
    st.html(
        '<div class="facts facts--stack">'
        f"<span>model <b>{escape(config.MODEL_NAME)}</b></span>"
        f"<span>version <b>{escape(config.MODEL_VERSION)}</b></span>"
        f"<span>prompt <b>{PROMPT_VERSION}</b></span>"
        f"<span>endpoint <b>{endpoint_state}</b></span>"
        f"<span>langfuse <b>{langfuse_state}</b></span></div>"
    )
    if st.button(
        "Wake up the endpoint",
        help="Do this right before the demo: a first call to check that it answers.",
    ):
        try:
            with st.spinner("Calling the endpoint…"):
                warmup = extract_live(
                    examples[0]["notes"] if examples else "Test note."
                )
            st.success(f"The endpoint answers ({warmup.latency_s:.1f} s).")
        except EndpointError as error:
            st.error(str(error))

page_header(FILE, "Paste notes. The model fills in the record.")

left, right = st.columns(2, gap="large")
current = state.demo_result

# -- Gauche : les notes ---------------------------------------------------------------
with left:
    st.html(label_html("Meeting notes"))
    if examples:
        st.pills(
            "Examples",
            [e["title"] for e in examples],
            key="example_pick",
            on_change=use_example,
            label_visibility="collapsed",
        )
    st.text_area(
        "Meeting notes",
        key="notes",
        height=200,
        label_visibility="collapsed",
        placeholder="Paste the raw notes here, in French, as the salesperson typed or dictated them.",
    )
    if st.button(
        "Fill in the record",
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
                        "No recorded answer for this text: replay only works with the examples.",
                        alert=True,
                    )
                )
        else:
            try:
                with st.spinner(
                    "The model is filling in the record… (5 to 15 s on a T4 GPU)"
                ):
                    result = extract_live(state.notes)
            except EndpointError as error:
                st.html(
                    banner_html(
                        f"{error} Fallback: switch the source to “{MODE_REPLAY}” in the sidebar.",
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
            '<div style="height:.8rem"></div>'
            + label_html("Where each field comes from")
        )
        st.html(
            highlighted_notes_html(current["notes"], current["result"].check.record)
        )

# -- Droite : la fiche ------------------------------------------------------------------
with right:
    st.html(label_html("CRM record"))
    if current is None:
        st.html(
            empty_html(
                "The record will appear here. Pick an example or paste notes, "
                "then click <b>Fill in the record</b>."
            )
        )
    else:
        result = current["result"]
        if result.source == "rejeu-fictif":
            st.html(
                banner_html(
                    "Replay · hand-written placeholder answer, waiting for a real recorded answer from the model.",
                    alert=True,
                )
            )
        elif result.source == "rejeu-enregistre":
            st.html(banner_html("Replay · model answer recorded in advance."))

        checks = [
            (
                "valid json" if result.check.json_valid else "invalid json",
                result.check.json_valid,
            ),
            (
                "valid schema" if result.check.schema_valid else "invalid schema",
                result.check.schema_valid,
            ),
        ]
        if result.latency_s is not None:
            checks.append((f"{result.latency_s:.1f} s", True))
        if result.verdict is not None:
            score = result.verdict[0]
            checks.append((f"LLM judge {score:g}/1", score == 1))

        record = result.check.record
        if record is None:
            st.html(refused_card_html(result.check.errors, checks))
        else:
            stamp = "validated" if current["validation"] is not None else "draft"
            st.html(
                record_card_html(record, current["notes"], stamp=stamp, checks=checks)
            )
        if result.verdict is not None:
            st.caption(f"LLM judge (Gemini): {result.verdict[1]}")
        with st.expander("Raw model answer"):
            st.code(result.answer or "(empty)", language="json")

        # -- Validation par le commercial : la vérité terrain envoyée à Langfuse -------
        if record is not None:
            st.html(
                '<div style="height:.6rem"></div>'
                + label_html("Validation by the salesperson")
            )
            if result.trace_id is None:
                st.caption(
                    "Replay or Langfuse off: feedback and validation are not sent to Langfuse."
                )
            thumbs = st.feedback("thumbs", key=f"thumbs_{current['id']}")
            if thumbs is not None and not current["thumbs_sent"]:
                try:
                    send_thumbs(result.trace_id, thumbs == 1)
                    current["thumbs_sent"] = True
                except Exception as error:  # noqa: BLE001  Langfuse arrêté : la démo continue
                    st.html(
                        banner_html(
                            f"Feedback not sent to Langfuse: {error}", alert=True
                        )
                    )

            with st.form(key=f"validation_{current['id']}", border=False):
                edited = {
                    key: validation_input(key, label, record.get(key))
                    for key, label in FIELDS
                }
                submitted = st.form_submit_button(
                    "Validate the record", type="primary", width="stretch"
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
                            f"Validation not sent to Langfuse: {error}", alert=True
                        )
                    )
            if current["validation"] is not None:
                sent = (
                    " · sent to Langfuse as the correct answer"
                    if result.trace_id
                    else ""
                )
                st.html(
                    banner_html(
                        f"Record validated · {current['validation']} field(s) corrected{sent}"
                    )
                )

nav_buttons(FILE)
