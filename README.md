# Agentic Workflow Project

## Description

Projet de cours LLMOps — flux de bout en bout (données, entraînement, registre, déploiement,
interface, monitoring) sur GCP.

**Cas d'usage : notes de réunion commerciale (français) -> fiche CRM JSON.**
Un commercial colle ses notes brutes, le modèle renvoie une fiche à 7 champs
(`company`, `contact_name`, `contact_role`, `need`, `budget_keur`, `deadline`, `next_action`).
`need` et `next_action` sont des listes fermées, les champs absents de la note valent `null`
(voir `src/crm_schema.py`). Modèle : Phi-3-mini-4k-instruct fine-tuné en LoRA.

Données : `data/crm_meeting_notes.csv` (558 notes 100 % synthétiques, générées par Gemini avec
contrôle croisé par une seconde extraction, voir `scripts/generate_crm_dataset.py`). Les notes
contenant des caractères de contrôle ou invisibles sont écartées (`has_corrupted_text`).
Régénération : `uv run --env-file .env python -m scripts.generate_crm_dataset --backend vertex`.

Évaluation (déterministe, sans LLM juge) : `valid_json`, `valid_schema`, exactitude par champ,
`exact_match`, `hallucinated_field`, `field_accuracy`.

## Prérequis

- Python 3.11.6
- [uv](https://docs.astral.sh/uv/) (gestionnaire de paquets)
- [Git](https://github.com/git-guides/install-git)
- [Docker](https://docs.docker.com/desktop/)

## Installation

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/emeret-as/agentic-workflow-project
   cd agentic-workflow-project
   ```

2. Créer l'environnement virtuel et installer les dépendances :
   ```bash
   uv sync
   ```

3. Configurer votre IDE pour utiliser l'environnement virtuel `.venv`.
   - `which python` doit pointer vers `.venv/bin/python`

## Packages principaux

| Package | Usage |
|---|---|
| `google-cloud-aiplatform` | Vertex AI (LLMs, embeddings) |
| `google-cloud-bigquery` | Requêtes SQL sur les données |
| `google-cloud-storage` | Accès aux buckets GCS |

## Variables d'environnement

Copier `.env.example` en `.env` et remplir les valeurs :

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GCP_PROJECT_ID` | ID du projet GCP |
| `GCP_REGION` | Région GCP (ex: `europe-west2`) |
| `GCP_BUCKET_NAME` | Nom du bucket GCS |

## Pipeline d'entraînement (sessions 2-3)

```bash
uv run --env-file .env python -m scripts.pipeline_runner
```

Lance une seule fois : chaque lancement crée un pipeline et réserve des GPU.

## Déploiement du modèle (session 4)

1. Enregistrer le modèle dans le Model Registry, avec le handler custom (`src/handler.py`)
   copié à la racine du dossier des artefacts :
   ```bash
   uv run --env-file .env python -m scripts.register_model_with_custom_handler \
       --model-uri gs://<bucket>/vertexai-pipeline-root/<...>/fine-tuning-component_<...>/model \
       --model-name emeret-ureboullet_model
   # Nouvelle version d'un modèle existant : ajouter --parent-model <ID du modèle>
   ```
2. Déployer le modèle sur un Endpoint depuis la console Vertex AI (n1-standard-8 + 1 T4,
   1 nœud min/max). Compter 15 à 30 minutes.
3. Renseigner `GCP_PROJECT_NUMBER` et `GCP_ENDPOINT_ID` dans `.env`, puis tester :
   ```bash
   curl -X POST \
     -H "Authorization: Bearer $(gcloud auth print-access-token)" \
     -H "Content-Type: application/json" \
     "https://europe-west2-aiplatform.googleapis.com/v1/projects/${GCP_PROJECT_NUMBER}/locations/europe-west2/endpoints/${GCP_ENDPOINT_ID}:predict" \
     -d "@${INPUT_DATA_FILE}"
   ```
4. **Supprimer l'endpoint après usage** : Vertex AI facture tant qu'il existe
   (pas de scale-to-zero, pas de pause).

## Application Chainlit et monitoring (sessions 4-5)

```bash
PYTHONPATH=. uv run --env-file .env chainlit run src/app/main.py
```

`PYTHONPATH=.` est nécessaire pour que l'app trouve le package `src`.

L'app (`src/app/main.py`) appelle l'endpoint avec les Application Default Credentials (usage de
développement : en production, utiliser un compte de service). Les notes de plus de 3000 caractères
sont refusées. Chaque message produit dans Langfuse :
- un span `User Message` (note brute -> fiche extraite) ;
- une generation imbriquée (prompt + paramètres -> sortie brute, modèle, version, latence) ;
- trois scores : `json_valid`, `schema_valid`, `names_grounded` (société et contact retrouvés
  dans la note).

Tests locaux sans GCP : `PYTHONPATH=. uv run --env-file .env python local_tests/crm_app_test.py`
et `local_tests/crm_metrics_test.py`.

Langfuse s'héberge en local avec Docker Compose
([tutoriel](https://langfuse.com/self-hosting/deployment/docker-compose)). Créer un projet et des
clés API sur http://localhost:3000, puis remplir `LANGFUSE_*` dans `.env`. Les évaluateurs
LLM-as-a-judge et les dashboards se configurent ensuite dans l'interface Langfuse.
