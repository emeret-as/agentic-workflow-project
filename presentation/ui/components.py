"""Morceaux d'interface en HTML : notes surlignées, fiche CRM, états vides.

Fonctions pures (sans Streamlit) : elles renvoient du HTML, ce qui permet de
les tester. Le style est dans ui/theme.py.
"""

from html import escape

from crm.field_check import (
    AMOUNT_PATTERN,
    CHECK,
    FOUND,
    TEXT_FIELDS,
    field_status,
    find_date,
    fold,
    parse_amounts,
)
from crm.schema import FIELDS, format_value
from rapidfuzz import fuzz

# Étiquette courte posée à côté de chaque passage surligné
FIELD_TAGS = {
    "company": "entreprise",
    "contact_name": "contact",
    "contact_role": "fonction",
    "need": "besoin",
    "budget_eur": "budget",
    "next_action": "action",
    "deadline": "échéance",
}
# Ressemblance minimale (0-100) pour dire « ce champ vient de ce passage »
_MIN_SCORE = 85


def _snap_to_words(notes: str, start: int, end: int) -> tuple[int, int]:
    while start > 0 and notes[start - 1].isalnum():
        start -= 1
    while end < len(notes) and notes[end].isalnum():
        end += 1
    return start, end


def find_source_span(key: str, value, notes: str) -> tuple[int, int] | None:
    """Retrouve dans les notes le passage d'où vient la valeur d'un champ.

    Besoin et prochaine action sont des catégories : pas de passage à surligner.
    """
    if value is None or not notes:
        return None
    if key == "budget_eur" and isinstance(value, int):
        for match in AMOUNT_PATTERN.finditer(notes):
            if value in parse_amounts(match.group(0)):
                start, end = match.start(), match.end()
                if start > 0 and notes[start - 1] in "$€£~":
                    start -= 1
                if notes[end : end + 2].strip().startswith("€"):
                    end = notes.index("€", end) + 1
                return start, end
        return None
    if key == "deadline":
        return find_date(value, notes)
    if key not in TEXT_FIELDS or not isinstance(value, str):
        return None
    alignment = fuzz.partial_ratio_alignment(fold(value), fold(notes))
    if alignment is None or alignment.score < _MIN_SCORE:
        return None
    return _snap_to_words(notes, alignment.dest_start, alignment.dest_end)


def source_spans(notes: str, record: dict) -> list[tuple[int, int, str]]:
    """Passages surlignés, triés, sans chevauchement."""
    spans = []
    for key, _ in FIELDS:
        span = find_source_span(key, record.get(key), notes)
        if span:
            spans.append((span[0], span[1], key))
    kept, last_end = [], -1
    for start, end, key in sorted(spans):
        if start >= last_end:
            kept.append((start, end, key))
            last_end = end
    return kept


def highlighted_notes_html(notes: str, record: dict) -> str:
    parts, position = [], 0
    for index, (start, end, key) in enumerate(source_spans(notes, record)):
        parts.append(escape(notes[position:start]))
        parts.append(
            f'<mark class="hl" style="--i:{index}">{escape(notes[start:end])}</mark>'
            f'<span class="hl__tag">{FIELD_TAGS[key]}</span>'
        )
        position = end
    parts.append(escape(notes[position:]))
    return f'<div class="notes">{"".join(parts)}</div>'


def _checks_html(checks: list[tuple[str, bool]]) -> str:
    if not checks:
        return ""
    items = "".join(
        f'<span class="{"" if ok else "is-bad"}">{escape(text)}</span>'
        for text, ok in checks
    )
    return f'<div class="record__checks">{items}</div>'


_STAMPS = {"draft": "Brouillon IA", "validated": "Validée", "refused": "Refusée"}


def _head_html(stamp: str) -> str:
    return (
        '<div class="record__head"><span class="record__title">Fiche CRM</span>'
        f'<span class="stamp stamp--{stamp}">{_STAMPS[stamp]}</span></div>'
    )


def record_card_html(
    record: dict,
    notes: str,
    stamp: str = "draft",
    checks: list[tuple[str, bool]] | None = None,
) -> str:
    """La fiche comme un formulaire : libellé, valeur, et d'où vient la valeur."""
    marked = {key for _, _, key in source_spans(notes, record)}
    rows = []
    for key, label in FIELDS:
        value = record.get(key)
        dt_class = ' class="is-marked"' if key in marked else ""
        if value is None:
            dd = '<dd class="is-empty">non mentionné</dd>'
        else:
            status = field_status(key, value, notes)
            note = ""
            if status == FOUND:
                note = '<span class="field__status">trouvé dans les notes</span>'
            elif status == CHECK:
                note = '<span class="field__status field__status--check">absent des notes · à vérifier</span>'
            dd = f"<dd>{escape(format_value(key, value))}{note}</dd>"
        rows.append(f'<div class="field"><dt{dt_class}>{label}</dt>{dd}</div>')
    return f'<div class="record">{_head_html(stamp)}<dl>{"".join(rows)}</dl>{_checks_html(checks or [])}</div>'


def refused_card_html(
    errors: list[str], checks: list[tuple[str, bool]] | None = None
) -> str:
    items = "".join(f"<li>{escape(error)}</li>" for error in errors)
    return (
        f'<div class="record">{_head_html("refused")}'
        '<p class="refused__lead">Le garde-fou a bloqué cette réponse : ce n\'est pas une fiche conforme, '
        "donc rien n'est affiché ni enregistré.</p>"
        f'<ul class="refused__errors">{items}</ul>{_checks_html(checks or [])}</div>'
    )


def label_html(text: str) -> str:
    return f'<div class="label">{escape(text)}</div>'


def empty_html(text_html: str) -> str:
    """État vide : dit ce qui va apparaître et comment l'obtenir (texte déjà en HTML)."""
    return f'<div class="empty">{text_html}</div>'


def banner_html(text: str, alert: bool = False) -> str:
    return (
        f'<div class="banner{" banner--alert" if alert else ""}">{escape(text)}</div>'
    )
