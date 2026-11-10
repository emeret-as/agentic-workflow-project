# Agentic Workflow Project

## Description

Projet de cours LLMOps — mise en place d'un environnement local et cloud pour des workflows agentiques avec GCP.

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
       --model-name yoda-phi-3-mini-4k-instruct
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

L'app (`src/app/main.py`) appelle l'endpoint avec un token `gcloud` (usage de développement
uniquement : en production, utiliser un compte de service). Chaque message produit dans Langfuse :
- un span `User Message` (message brut -> réponse extraite) ;
- une generation imbriquée (prompt + paramètres -> sortie brute, modèle, version, latence).

Langfuse s'héberge en local avec Docker Compose
([tutoriel](https://langfuse.com/self-hosting/deployment/docker-compose)). Créer un projet et des
clés API sur http://localhost:3000, puis remplir `LANGFUSE_*` dans `.env`. L'évaluateur
LLM-as-a-judge « Yoda-ness » et le dashboard se configurent ensuite dans l'interface Langfuse.
