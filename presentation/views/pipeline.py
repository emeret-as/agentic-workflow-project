from html import escape

import streamlit as st
from crm import config
from crm.prompt import PROMPT_VERSION
from ui.common import nav_buttons, page_header

FILE = "views/pipeline.py"

page_header(
    FILE,
    "The course workflow, from data to monitoring.",
    "Every step runs on Google Cloud as in the practice sessions; the data, the prompt and "
    "the metrics are ours.",
)


def step(name: str, detail: str, css_class: str = "") -> str:
    class_attr = f' class="{css_class}"' if css_class else ""
    return f"<li{class_attr}><b>{name}</b><span>{detail}</span></li>"


st.html(
    '<div class="lanes">'
    '<section class="lane"><div class="label">Prepare</div><ol class="flowlist">'
    + step(
        "Gemini (Vertex AI)",
        "draws a record, then writes the note: 6 styles, 3 lengths, one distractor",
    )
    + step(
        "Cross-check",
        "a second extraction must find the same record, otherwise the note is dropped",
    )
    + step("GCS", "558 notes kept, versioned in the repo and copied to the bucket")
    + '</ol></section><div class="lane-arrow"></div>'
    '<section class="lane lane--pipeline"><div class="label">Train · Vertex AI pipeline</div><ol class="flowlist">'
    + step(
        "Transformation",
        f"Phi-3 chat format, prompt {PROMPT_VERSION}; 502 training notes, 56 test notes",
    )
    + step(
        "Fine-tuning",
        "LoRA r=8 on Phi-3 loaded in 4 bits, 3 epochs, 79 min on a T4 GPU",
    )
    + step(
        "Inference",
        "the fine-tuned model, and base Phi-3 in a second pipeline, on the same 56 notes",
    )
    + step(
        "Evaluation",
        "JSON, schema, exact record, invented field, field by field → Results page",
    )
    + '</ol></section><div class="lane-arrow"></div>'
    '<section class="lane"><div class="label">Serve and monitor</div><ol class="flowlist">'
    + step("Model Registry", "emeret-crm-phi3, registered with its handler")
    + step("Endpoint", "n1-standard-4 + T4, deployed for the demo, deleted right after")
    + step("Streamlit app", "this presentation and the live demo", "is-app")
    + step("Langfuse", "self-hosted: traces, scores, LLM judge, dashboard")
    + "</ol></section></div>"
)

st.html(
    '<div class="facts">'
    "<span>base model <b>Phi-3-mini-4k-instruct</b></span>"
    f"<span>served model <b>{escape(config.MODEL_NAME)} v{escape(config.MODEL_VERSION)}</b></span>"
    f"<span>prompt <b>{PROMPT_VERSION}</b></span>"
    "<span>run <b>model-training-pipeline-20261112183827</b></span></div>"
)

nav_buttons(FILE)
