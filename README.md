# Agentic Workflow Project

## Description

Projet de cours LLMOps — flux de bout en bout (données, entraînement, registre, déploiement,
interface, monitoring) sur GCP.

**Cas d'usage : notes de réunion commerciale (français) -> fiche CRM JSON.**
Un commercial colle ses notes brutes, le modèle renvoie une fiche à 7 champs
(`company`, `contact_name`, `contact_role`, `need`, `budget_eur`, `next_action`, `deadline`).
`need` et `next_action` sont des listes fermées, les champs absents de la note valent `null`
(voir `src/crm_schema.py`). Modèle : Phi-3-mini-4k-instruct fine-tuné en LoRA.

Données : `data/crm_meeting_notes.csv` (558 notes 100 % synthétiques, générées par Gemini avec
contrôle croisé par une seconde extraction, voir `scripts/generate_crm_dataset.py`). Les notes
contenant des caractères de contrôle ou invisibles sont écartées (`has_corrupted_text`).
Régénération : `uv run --env-file .env python -m scripts.generate_crm_dataset --backend vertex`.

Évaluation (déterministe, sans LLM juge) : `valid_json`, `valid_schema`, exactitude par champ,
`exact_match`, `hallucinated_field`, `field_accuracy`.

## Résultats (56 notes de test, même évaluation pour les deux modèles)

| Mesure | Phi-3 de base | Phi-3 fine-tuné (LoRA) |
|---|---|---|
| JSON valide | 88 % | 100 % |
| Schéma valide (types, listes fermées) | 0 % | 100 % |
| Fiche exacte (7 champs justes) | 0 % | 98,2 % |
| Champs justes | 53 % | 99,7 % |
| Fiches avec un champ inventé | 27 % | 1,8 % |

Runs : `model-training-pipeline-20261112183827` et `base-model-evaluation-pipeline-20261112212113`.

- **Pourquoi le schéma du modèle de base est à 0 %** : le prompt ne donne pas les listes fermées,
  donc Phi-3 de base ne peut pas les deviner. Sur les champs recopiés (entreprise, contact,
  budget), l'écart est de 12 à 20 points.
- **L'unique erreur du modèle fine-tuné** : une date de séminaire reprise comme échéance.
- **Sur l'endpoint** (float16 au lieu de 4 bits) : 56/56 fiches exactes, 5,7 s par note (médiane).

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

Modèle de base (référence) : `scripts/base_model_evaluation_runner.py` lance
`base_model_evaluation_pipeline`. Ce pipeline réutilise le jeu de test et le dossier du modèle
d'un run d'entraînement, puis passe Phi-3 **sans** adaptateurs LoRA dans les mêmes composants
d'inférence et d'évaluation (`use_base_model=True`) :
```bash
uv run --env-file .env python -m scripts.base_model_evaluation_runner \
    --training-run model-training-pipeline-20261112183827
```

## Déploiement du modèle (session 4)

1. Enregistrer le modèle dans le Model Registry, avec le handler custom (`src/handler.py`)
   copié à la racine du dossier des artefacts. Le modèle CRM est enregistré sous
   `emeret-crm-phi3` (modèle distinct du modèle Yoda `emeret-ureboullet_model`) :
   ```bash
   uv run --env-file .env python -m scripts.register_model_with_custom_handler \
       --model-uri gs://<bucket>/vertexai-pipeline-root/<...>/fine-tuning-component_<...>/model \
       --model-name emeret-crm-phi3
   # Nouvelle version d'un modèle existant : ajouter --parent-model <ID du modèle>
   ```
2. Déployer le modèle sur un Endpoint (1 GPU T4, 1 nœud min/max, 15 à 30 minutes).
   `n1-standard-4` évite l'erreur de quota `CustomModelServingCPUsPerProjectPerRegion`
   quand les endpoints des autres équipes occupent les CPU :
   ```bash
   uv run --env-file .env python -m scripts.deploy_endpoint \
       --model emeret-crm-phi3 --endpoint-name emeret-crm-endpoint --machine-type n1-standard-4
   ```
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

### Langfuse auto-hébergé (session 5)

1. Cloner Langfuse **à côté** du repo, puis créer un fichier `.env` dans le dossier
   `langfuse` (il n'est jamais commité). Les variables `LANGFUSE_INIT_*` créent au premier
   démarrage l'organisation, le projet (`crm-notes`), ses clés API et un compte
   administrateur :
   ```bash
   git clone --depth 1 https://github.com/langfuse/langfuse.git ../langfuse
   ```
   Variables à mettre dans `../langfuse/.env` :
   `NEXTAUTH_SECRET`, `SALT`, `ENCRYPTION_KEY` (`openssl rand -hex 32`),
   `LANGFUSE_INIT_ORG_ID`, `LANGFUSE_INIT_PROJECT_ID`,
   `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`, `LANGFUSE_INIT_PROJECT_SECRET_KEY`,
   `LANGFUSE_INIT_USER_EMAIL`, `LANGFUSE_INIT_USER_PASSWORD`.
2. Si un Postgres tourne déjà sur le Mac (port 5432 pris), exposer celui de Langfuse sur
   5433 avec un `docker-compose.override.yml` :
   ```yaml
   services:
     postgres:
       ports: !override
         - 127.0.0.1:5433:5432
   ```
   Puis `docker compose up -d` dans `../langfuse`. L'interface est sur http://localhost:3000.
3. Copier les deux clés du projet dans `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY` du
   `.env` du repo, avec `LANGFUSE_HOST=http://localhost:3000`.
4. Remplir Langfuse avec de vraies traces (endpoint déployé). Ce script envoie les 56 notes
   de test et 7 notes pièges par la même fonction que l'app. Il ajoute les scores
   `exact_match` (notes de test) et `source`, puis sauvegarde les sorties dans
   `data/endpoint_outputs.json` :
   ```bash
   PYTHONPATH=. uv run --env-file .env python -m scripts.send_test_notes \
       --eval-results gs://<bucket>/vertexai-pipeline-root/<...>/evaluation-component_<...>/evaluation_results
   ```
5. Dashboard : `uv run --env-file .env python -m scripts.create_langfuse_dashboard`. Il crée
   « Fiches CRM - suivi en production » par l'API publique : notes traitées, qualité des
   fiches, qualité dans le temps, latence p50/p95 de l'endpoint.
6. Juge LLM : connexion LLM (clé Gemini) et évaluateur `fidelite_fiche`, créés dans
   l'interface (l'API publique ne crée pas d'évaluateurs). Le prompt et les réglages sont
   dans `docs/langfuse_judge_prompt.md`.

Langfuse v4 tourne en mode `events_only` : les anciennes routes de lecture
(`/api/public/traces`, `/api/public/scores`) répondent par une erreur. Pour relire les
données, utiliser `/api/public/v2/observations` et `/api/public/v3/scores`.

## Présentation (session 6)

Toute la présentation se fait dans une app Streamlit (`presentation/`) en 7 pages : brief, démo en
direct, pipeline, résultats, monitoring, problèmes rencontrés, coûts et IA responsable. L'app
réutilise le schéma du projet (`src/crm_schema.py`) et trace ses appels dans Langfuse, comme l'app
Chainlit (mêmes noms de span, de generation et de scores).

```bash
cd presentation && uv run streamlit run app.py
```

- **Démo « Modèle en ligne »** : appelle l'endpoint, si `GCP_ENDPOINT_ID` est renseigné dans `.env`.
- **Démo « Rejeu enregistré »** : réponses réelles de l'endpoint, enregistrées le 12/11 dans
  `presentation/data/replay.json`. C'est le secours si l'endpoint ne répond pas.
- **Page Résultats** : lit `presentation/data/results.json`, produit par
  `uv run --env-file .env python -m scripts.build_results --finetuned-run <run> --base-run <run>`.
- Tests : `uv run python -m pytest presentation/tests -q`.

Jour de la démo : redéployer l'endpoint environ 30 minutes avant (`scripts.deploy_endpoint`),
renseigner `GCP_ENDPOINT_ID`, cliquer « Réveiller l'endpoint » dans la barre latérale de la démo,
puis supprimer l'endpoint juste après.
