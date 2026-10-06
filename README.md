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
