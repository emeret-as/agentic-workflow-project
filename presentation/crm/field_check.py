"""Statut de chaque champ de la fiche par rapport aux notes, et passage d'origine.

- Entreprise, interlocuteur, fonction : le texte doit se retrouver dans les notes.
- Budget : le montant doit apparaître dans les notes (« 124 k€ », « 297 000 euros »).
- Échéance : la date doit apparaître (« 26/02/2027 », « 26 février 2027 »…).
- Besoin et prochaine action sont des catégories choisies dans une liste : pas
  de vérification mot à mot.
Un champ introuvable n'est pas forcément faux (« fin janvier » → 2027-01-31),
mais il mérite un coup d'œil : c'est ce que dit l'interface.
"""

import re
import unicodedata
from datetime import date

from rapidfuzz import fuzz

from src.crm_schema import normalize

FOUND = "found"  # la valeur se retrouve dans les notes
CHECK = "check"  # introuvable dans les notes : peut-être inventée
MISSING = "missing"  # null : non mentionné
NOT_CHECKED = "not_checked"  # catégorie : pas de vérification

TEXT_FIELDS = {"company", "contact_name", "contact_role"}
CHECKED_FIELDS = TEXT_FIELDS | {"budget_eur", "deadline"}

# Un montant : chiffres (séparateurs de milliers acceptés), éventuellement « k » ou « M ».
# Les lookarounds évitent de prendre « 1 » dans « 18e » ou un morceau d'un autre nombre.
AMOUNT_PATTERN = re.compile(
    r"(?<![\d.,])(\d+(?:[.,\s ]\d{3})*(?:[.,]\d+)?)\s*([kKmM])?(?![a-zA-Z\d])"
)

_MONTHS = [
    "janvier",
    "fevrier",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "aout",
    "septembre",
    "octobre",
    "novembre",
    "decembre",
]


def parse_amounts(text: str) -> set[int]:
    """Montants d'un texte : « 124 k€ », « 297 000 euros », « 1,2M » → en euros."""
    amounts = set()
    for number, multiplier in AMOUNT_PATTERN.findall(text):
        digits = re.sub(r"[\s ]", "", number)
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", digits):  # « 50.000 », « 50,000 »
            digits = re.sub(r"[.,]", "", digits)
        try:
            value = float(digits.replace(",", "."))
        except ValueError:
            continue
        if multiplier.lower() == "k":
            value *= 1_000
        elif multiplier.lower() == "m":
            value *= 1_000_000
        amounts.add(round(value))
    return amounts


def date_patterns(iso_date: str) -> list[re.Pattern]:
    """Façons d'écrire une date dans des notes, de la plus précise à la moins précise."""
    try:
        day = date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return []
    d, m, y = day.day, day.month, day.year
    month = _MONTHS[m - 1]
    day_word = "(?:1er|1)" if d == 1 else str(d)
    return [
        re.compile(rf"(?<!\d)0?{d}[/.-]0?{m}[/.-](?:{y}|{y % 100:02d})(?!\d)"),
        re.compile(rf"(?<!\d){day_word}\s+{month}\s+{y}"),
        re.compile(rf"(?<!\d)0?{d}[/.-]0?{m}(?![/.\-\d])"),
        re.compile(rf"(?<!\d){day_word}\s+{month}"),
    ]


def fold(text: str) -> str:
    """Minuscules sans accents, caractère par caractère : les positions restent valables."""
    return "".join(
        (unicodedata.normalize("NFKD", char)[:1].lower()[:1] or char) for char in text
    )


def find_date(iso_date: str, notes: str) -> tuple[int, int] | None:
    """Position de la date dans les notes (recherche sans accents ni majuscules)."""
    text = fold(notes)
    for pattern in date_patterns(iso_date):
        match = pattern.search(text)
        if match:
            return match.start(), match.end()
    return None


def field_status(key: str, value, notes: str) -> str:
    """Renvoie le statut d'un champ (voir les constantes en haut du fichier)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return MISSING
    if key not in CHECKED_FIELDS:
        return NOT_CHECKED
    if key == "budget_eur":
        return (
            FOUND if isinstance(value, int) and value in parse_amounts(notes) else CHECK
        )
    if key == "deadline":
        return FOUND if find_date(value, notes) else CHECK
    score = fuzz.partial_ratio(normalize(str(value)), normalize(notes))
    return FOUND if score >= 85 else CHECK
