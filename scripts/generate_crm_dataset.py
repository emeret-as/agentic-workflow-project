"""Generate the synthetic CRM dataset (meeting notes -> CRM record).

Principe : on tire d'abord la fiche CRM de référence (vérité terrain exacte),
puis Gemini rédige la note de réunion correspondante. Une seconde passe
d'extraction indépendante sert de contrôle : les notes pour lesquelles elle ne
retrouve pas la fiche sont écartées (information ambiguë ou mal rédigée).

Usage :
    uv run --env-file .env python -m scripts.generate_crm_dataset \
        --n 700 --out data/crm_meeting_notes.csv [--backend vertex]

Backend `aistudio` (défaut) : clé GEMINI_API_KEY du .env, limitée à 20 requêtes
par jour en offre gratuite. Backend `vertex` : projet GCP du .env et ADC, facturé
au projet (quelques centimes pour 700 notes). Toutes les sociétés et personnes sont
fictives : aucune donnée client réelle n'est utilisée.
"""

import argparse
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any

import pandas as pd
from google import genai
from google.genai import types

from src.constants import PROJECT_ID
from src.crm_schema import (
    FIELDS,
    NEED_DESCRIPTIONS,
    NEEDS,
    NEXT_ACTION_DESCRIPTIONS,
    NEXT_ACTIONS,
    has_corrupted_text,
    is_valid_record,
    normalize,
    parse_json,
    to_json,
)

DEFAULT_MODEL = "gemini-3.5-flash"
BATCH_SIZE = 5
MAX_WORKERS = 4

# -- Tirage des fiches ---------------------------------------------------------
SECTORS = [
    "Brasserie", "Transports", "Clinique", "Laboratoires", "Menuiseries",
    "Assurances", "Imprimerie", "Cabinet", "Groupe", "Logistique",
    "Coopérative", "Maison", "Fonderie", "Textiles", "Pharmacie", "Domaine",
]  # fmt: skip
STEMS = [
    "Delmotte", "Kervalec", "Saint-Aubin", "Marchetti", "Beaulieu", "Vasseur",
    "Montcalm", "Lefranc", "Ardenne", "Rivoire", "Castelnau", "Perrin",
    "Valmont", "Duchêne", "Ferrand", "Lagrange", "Sauvage", "Tessier",
]  # fmt: skip
FIRST_NAMES = [
    ("Camille", "f"), ("Julien", "m"), ("Sophie", "f"), ("Thomas", "m"),
    ("Élodie", "f"), ("Nicolas", "m"), ("Amélie", "f"), ("Mathieu", "m"),
    ("Claire", "f"), ("Antoine", "m"), ("Laure", "f"), ("Maxime", "m"),
    ("Inès", "f"), ("Hugo", "m"), ("Sarah", "f"), ("Romain", "m"),
    ("Léa", "f"), ("Karim", "m"), ("Nadia", "f"), ("Pierre", "m"),
]  # fmt: skip
LAST_NAMES = [
    "Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Simon", "Michel",
    "Garcia", "Roux", "Fournier", "Girard", "Bonnet", "Lambert", "Faure",
    "Mercier", "Blanc", "Guerin", "Muller", "Henry", "Chevalier",
]  # fmt: skip
ROLES = [
    ("Directeur informatique", "Directrice informatique"),
    ("Directeur commercial", "Directrice commerciale"),
    ("DSI", "DSI"),
    ("Responsable achats", "Responsable achats"),
    ("Directeur général", "Directrice générale"),
    ("Responsable marketing", "Responsable marketing"),
    ("Directeur financier", "Directrice financière"),
    ("Chef de projet digital", "Cheffe de projet digital"),
    ("Responsable innovation", "Responsable innovation"),
]  # fmt: skip

STYLES = {
    "bullets": "liste à puces rapide, style abrégé",
    "telegraphic": "notes télégraphiques prises pendant l'appel, abréviations et une ou deux fautes de frappe",
    "email": "court mail de compte rendu à un collègue",
    "prose": "paragraphe rédigé de compte rendu",
    "dictated": "transcription dictée à l'oral, phrases un peu désordonnées",
    "crm_comment": "commentaire rapide saisi dans un CRM après un rendez-vous",
}
LENGTHS = {
    "short": "2 à 3 phrases (environ 40 mots)",
    "medium": "5 à 7 phrases (environ 100 mots)",
    "long": "10 à 14 phrases (environ 180 mots) avec des détails annexes",
}
DISTRACTORS = {
    "none": "aucun élément parasite",
    "competitor": "cite un concurrent du client, avec un nom de société fictif différent",
    "colleague": "cite un collègue de l'équipe commerciale, avec un prénom différent du contact",
    "figure": "cite un chiffre sans rapport avec le budget (effectif, chiffre d'affaires, nombre de sites)",
    "date": "cite une date sans rapport avec l'échéance (congés, salon), clairement présentée comme étrangère au projet",
}


def sample_record(rng: random.Random) -> dict[str, Any]:
    """Draw one ground-truth CRM record."""
    has_contact = rng.random() < 0.8
    first_name, gender = rng.choice(FIRST_NAMES)
    contact_name = f"{first_name} {rng.choice(LAST_NAMES)}" if has_contact else None
    has_role = rng.random() < (0.75 if has_contact else 0.5)
    # Le titre est accordé au genre du prénom ; sans contact, on tire au hasard
    role = rng.choice(ROLES)[0 if gender == "m" else 1] if has_role else None
    deadline = None
    if rng.random() < 0.55:
        deadline = (date(2027, 1, 5) + timedelta(days=rng.randint(0, 350))).isoformat()
    return {
        "company": f"{rng.choice(SECTORS)} {rng.choice(STEMS)}",
        "contact_name": contact_name,
        "contact_role": role,
        "need": rng.choice(NEEDS),
        "budget_eur": rng.randrange(5_000, 300_001, 500)
        if rng.random() < 0.6
        else None,
        "next_action": rng.choice(NEXT_ACTIONS),
        "deadline": deadline,
    }


def sample_item(rng: random.Random) -> dict[str, Any]:
    """Draw a record plus the writing instructions for its note."""
    return {
        "record": sample_record(rng),
        "style": rng.choice(list(STYLES)),
        "length": rng.choice(list(LENGTHS)),
        "distractor": rng.choice(list(DISTRACTORS)),
    }


# -- Appels Gemini -------------------------------------------------------------
def call_json_list(
    client: genai.Client, model: str, prompt: str, expected_len: int, retries: int = 5
) -> list[str] | None:
    """Call Gemini and return a JSON array of strings of the expected length."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=list[str],
        temperature=1.0,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
            items = json.loads(response.text)
            if (
                isinstance(items, list)
                and len(items) == expected_len
                and all(isinstance(item, str) and item.strip() for item in items)
            ):
                return items
        except Exception as error:  # noqa: BLE001 - réseau, quota, JSON invalide
            print(f"  tentative {attempt + 1}/{retries} échouée : {str(error)[:120]}")
        time.sleep(2**attempt)
    return None


def writing_prompt(items: list[dict[str, Any]]) -> str:
    """Build the prompt asking Gemini to write one note per record."""
    blocks = []
    for index, item in enumerate(items, start=1):
        record = item["record"]
        blocks.append(
            f"Fiche {index} : {to_json(record)}\n"
            f"  besoin (à reformuler librement) : {NEED_DESCRIPTIONS[record['need']]}\n"
            f"  action suivante (à reformuler librement) : "
            f"{NEXT_ACTION_DESCRIPTIONS[record['next_action']]}\n"
            f"  style : {STYLES[item['style']]}\n"
            f"  longueur : {LENGTHS[item['length']]}\n"
            f"  élément parasite : {DISTRACTORS[item['distractor']]}"
        )
    return (
        "Tu rédiges des notes de réunion commerciale réalistes, en français, pour un "
        "jeu de données synthétique. Pour CHAQUE fiche ci-dessous, écris UNE note "
        "dont on peut retrouver exactement les informations de la fiche.\n\n"
        "Règles :\n"
        "- Les noms de sociétés et de personnes sont fictifs : utilise-les tels quels.\n"
        "- Écris le nom de la société en entier et, s'il existe, le nom du contact en "
        "entier (prénom et nom) au moins une fois.\n"
        "- Si un rôle est donné, cite-le mot pour mot.\n"
        "- Exprime le budget en euros avec un format varié (ex. « 80 k€ », « environ "
        "80 000 euros »), à la valeur exacte.\n"
        "- Exprime l'échéance comme une date complète (jour, mois, année), au format "
        "varié (« le 14 mars 2027 » ou « 14/03/2027 »).\n"
        "- Une valeur null ne doit apparaître d'aucune façon dans la note.\n"
        "- Reformule le besoin et l'action suivante avec tes propres mots. N'écris "
        "jamais les identifiants techniques (comme crm_migration).\n"
        "- Respecte le style, la longueur et l'élément parasite demandés. Un élément "
        "parasite ne doit pas pouvoir être confondu avec une information de la fiche.\n"
        "- Aucun JSON, aucun titre, aucune mention « fiche ».\n\n"
        + "\n\n".join(blocks)
        + f"\n\nRetourne un tableau JSON de {len(items)} chaînes (les notes), dans "
        "l'ordre des fiches."
    )


def extraction_prompt(notes: list[str]) -> str:
    """Build the prompt asking Gemini to extract the record from each note."""
    needs = "\n".join(f"  {key} : {text}" for key, text in NEED_DESCRIPTIONS.items())
    actions = "\n".join(
        f"  {key} : {text}" for key, text in NEXT_ACTION_DESCRIPTIONS.items()
    )
    numbered = "\n\n".join(f"Note {i}:\n{note}" for i, note in enumerate(notes, 1))
    return (
        "Pour chaque note de réunion, extrais la fiche CRM sous forme d'objet JSON "
        f"avec exactement ces clés, dans cet ordre : {', '.join(FIELDS)}.\n"
        "- company, contact_name, contact_role : texte de la note, ou null si absent.\n"
        "- need : une des valeurs suivantes :\n" + needs + "\n"
        "- budget_eur : entier en euros, ou null si aucun budget du client.\n"
        "- next_action : une des valeurs suivantes :\n" + actions + "\n"
        "- deadline : date AAAA-MM-JJ de l'échéance du projet, ou null si absente.\n\n"
        + numbered
        + f"\n\nRetourne un tableau JSON de {len(notes)} chaînes, chacune étant un "
        "objet JSON, dans l'ordre des notes."
    )


def process_batch(
    client: genai.Client, model: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Write the notes of a batch and cross-check them with an independent extraction."""
    notes = call_json_list(client, model, writing_prompt(items), len(items))
    if notes is None:
        return []
    extractions = call_json_list(client, model, extraction_prompt(notes), len(notes))
    if extractions is None:
        return []
    rows = []
    for item, note, extracted_text in zip(items, notes, extractions, strict=True):
        truth = item["record"]
        extracted = parse_json(extracted_text)
        mismatches = [
            field
            for field in FIELDS
            if extracted is None
            or normalize(extracted.get(field)) != normalize(truth[field])
        ]
        rows.append(
            {
                "note": note.strip(),
                "record": to_json(truth),
                "style": item["style"],
                "length": item["length"],
                "distractor": item["distractor"],
                "mismatches": ",".join(mismatches),
            }
        )
    return rows


def main() -> None:
    """Generate, cross-check and save the dataset."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, required=True, help="Notes à générer")
    parser.add_argument("--out", required=True, help="CSV de sortie")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--backend", choices=["aistudio", "vertex"], default="aistudio")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    items = [sample_item(rng) for _ in range(args.n)]
    for item in items:
        assert is_valid_record(item["record"]), item["record"]
    batches = [items[i : i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]

    if args.backend == "vertex":
        # gemini-3.5-flash n'est servi que depuis la région `global`
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    else:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(process_batch, client, args.model, b) for b in batches]
        for done, future in enumerate(futures, start=1):
            rows.extend(future.result())
            print(f"lot {done}/{len(batches)} : {len(rows)} notes générées")

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("Aucune note générée (vérifier GEMINI_API_KEY et le quota)")

    # Contrôle croisé : une note dont l'extraction diffère est ambiguë, on l'écarte
    corrupted = df["note"].map(has_corrupted_text)
    print(f"{corrupted.sum()} notes écartées : caractères corrompus")
    kept = df[(df["mismatches"] == "") & ~corrupted].drop_duplicates(subset="note")
    print(f"\n{len(df)} générées, {len(kept)} conservées ({len(kept) / len(df):.0%})")
    for field in FIELDS:
        rate = df["mismatches"].str.split(",").map(lambda m, f=field: f in m).mean()
        print(f"  désaccord sur {field:13s}: {rate:.1%}")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    kept.drop(columns="mismatches").to_csv(args.out, index=False)
    print(f"Écrit : {args.out}")


if __name__ == "__main__":
    main()
