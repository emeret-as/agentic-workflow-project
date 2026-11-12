# Passation du projet Agentic Workflow (LLMOps)

Document destiné à un assistant de codage agentique qui reprend le projet. Il décrit l'objectif,
l'état exact au 12/11/2026 à 19h20 UTC, les pièges déjà rencontrés et ce qu'il reste à faire.
Répondre à l'utilisateur en **français**. Ne jamais afficher de secret (clés Gemini, Langfuse,
mots de passe).

## 1. Le projet

Cours LLMOps / Agentic Workflows (prof : Mathieu Soul, Albert School, MSc Data & AI).

- Notation : 50 % projet, 50 % examen écrit sans IA. Équipe de 2 à 3 personnes.
- Livrable : un flux LLMOps de bout en bout (orchestration, registre, déploiement, interface,
  monitoring) sur un cas d'usage de génération de texte choisi par l'équipe.
- Présentation à la dernière session (session 6) : **AI product brief**, **démo en direct**,
  problèmes rencontrés et changements effectués.
- Budget cloud indicatif : moins de 50 $.
- Le programme du cours (`Courses/session1_slides.pdf`) a été adapté à un cas d'usage personnel : les
  exemples Yoda du cours ont été remplacés par le cas CRM ci-dessous.

**Cas d'usage retenu :** notes de réunion commerciale en français -> fiche CRM JSON à 7 champs
(`company`, `contact_name`, `contact_role`, `need`, `budget_keur`, `deadline`, `next_action`).
`need` et `next_action` sont des listes fermées ; un champ absent de la note vaut `null`.
Modèle : `microsoft/Phi-3-mini-4k-instruct` fine-tuné en LoRA. Données 100 % synthétiques (Gemini).
Évaluation déterministe, sans LLM juge.

## 2. Infrastructure

| Élément | Valeur |
|---|---|
| Projet GCP | `agentics-workflows-510809` (numéro `123905721265`) |
| Région | `europe-west2` (seule région avec quota GPU) |
| Bucket | `emeret-llmops` |
| Repo GitHub | https://github.com/emeret-as/agentic-workflow-project |
| Branche de travail | `crm-use-case` (poussée sur GitHub, **pas de PR** : on travaille directement dessus) |
| Modèle Yoda dans le registre | `models/6374284521612771328`, version 1, nommé `emeret-ureboullet_model` |

Données : `data/crm_meeting_notes.csv` (558 notes, versionné), copie sur
`gs://emeret-llmops/crm_meeting_notes.csv` (`RAW_DATASET_URI` dans `src/constants.py`).

## 3. État du code (branche `crm-use-case`, arbre propre)

Commits : `1803e59` (pipeline CRM), `2debd86` (app Chainlit CRM, normalisation sans accents),
`1751d14` (README), puis ce fichier. Les branches `session-4-deployment` (jusqu'à `82e78ab`) et
`crm-use-case` sont **poussées** sur `origin`. Récupérer le travail avec
`git fetch && git checkout crm-use-case`.

Pousser nécessite d'être connecté à GitHub avec un compte ayant accès en écriture à
`emeret-as/agentic-workflow-project` (vérifier avec `gh auth status`). Un 403 « denied to
emeret-perso » signifie que `gh` utilise le mauvais compte : `gh auth switch`.

Fichiers clés :
- `src/crm_schema.py` : schéma, listes fermées, consigne, `build_user_content`, `parse_json`,
  `is_valid_record`, `has_corrupted_text`, `normalize` (casse, accents, espaces).
- `scripts/generate_crm_dataset.py` : génération des données (`--backend vertex|aistudio`).
- `src/pipeline_components/{data_transformation,fine_tuning,inference,evaluation}_component.py`.
  Les composants Kubeflow ne peuvent pas importer `src/crm_schema.py` : ils en **dupliquent**
  les parties utiles (un test vérifie l'alignement des copies, ne pas le casser).
- `src/handler.py` : `EndpointHandler` du modèle servi (`max_new_tokens=160`).
- `scripts/register_model_with_custom_handler.py`, `scripts/deploy_endpoint.py` (`--delete`).
- `src/app/main.py` : app Chainlit CRM (ADC, limite d'entrée 3000 caractères, scores Langfuse
  `json_valid`, `schema_valid`, `names_grounded`).
- Tests locaux (sans GCP) : `local_tests/crm_metrics_test.py`, `local_tests/crm_app_test.py`.

Validation (tout passe à ce jour) :
```bash
PYTHONPATH=. uv run --env-file .env python local_tests/crm_app_test.py
PYTHONPATH=. uv run --env-file .env python local_tests/crm_metrics_test.py
uvx ruff check . && uvx ruff format --check src scripts local_tests/crm_*.py
```
`ruff format --check .` signale 2 anciens fichiers de tests Yoda (`local_tests/evaluation_test.py`
et un autre) : ils ne sont pas à nous, ne pas les reformater.

## 4. Pipeline d'entraînement CRM : où on en est

Job : `projects/123905721265/locations/europe-west2/pipelineJobs/model-training-pipeline-20261112183827`
(lancé à 17h38 UTC).

| Étape | État à 19h20 UTC |
|---|---|
| data-transformation | terminée (11 min) |
| fine-tuning | terminée (1 h 23 min) |
| inference | marquée en cours, mais son job Vertex était en `PENDING` (attente de GPU) |
| evaluation | en attente |

Résultats d'entraînement : `eval_loss` = 0,7596, `train_loss` = 0,9427 (84 étapes, 3 epochs,
LoRA r=8, 12,6 M paramètres entraînables).

**URI du modèle entraîné** (déjà sauvegardé, utilisable même si l'inférence échoue) :
`gs://emeret-llmops/vertexai-pipeline-root/123905721265/model-training-pipeline-20261112183827/fine-tuning-component_9118750344375959552/model`

Suivre le pipeline :
```bash
uv run --env-file .env python -W ignore -c "
from google.cloud import aiplatform as a
a.init(project='agentics-workflows-510809', location='europe-west2')
p=a.PipelineJob.get('projects/123905721265/locations/europe-west2/pipelineJobs/model-training-pipeline-20261112183827')
print(p.state.name)
for t in p.task_details: print(t.task_name, t.state.name)
"
```
Les métriques d'évaluation se lisent dans les sorties de la tâche `evaluation-component`
(`task_details[...].outputs`, artefact `metrics`) : `valid_json_mean`, `exact_match_mean`,
`field_accuracy_mean`, `hallucinated_field_mean`, etc. Si le pipeline est en échec, **ne pas
en relancer un sans vérifier d'abord la cause** (voir règles §5) ; si seule l'inférence a échoué,
corriger puis relancer le pipeline (l'entraînement est refait, 1 h 20).

Durées observées (T4, float32, 4 bits, gradient checkpointing) : ~52 s par étape, démarrages
de conteneurs de 5 à 11 minutes, attentes de GPU imprévisibles (quota partagé avec les autres
élèves). Prévoir large.

## 5. Règles et pièges à respecter

Choix techniques à ne pas défaire :
- versions pinnées avec `==` ; `langchain-community==0.4.1` ; pas de `BleuScore` ;
- `bnb_4bit_compute_dtype=float32` (le T4 ne gère pas le bfloat16) ;
- réparation de la colonne `messages` (regex `\}\s*\{` -> `}, {` puis `ast.literal_eval`) ;
- image de service : `peft==0.13.2` et `transformers==4.46.*`.

Coûts et ressources :
- Un endpoint Vertex facture en continu (pas de scale-to-zero). **Toujours le supprimer après
  usage** : `uv run --env-file .env python -m scripts.deploy_endpoint --delete <ENDPOINT_ID>`.
  Demander à l'utilisateur avant d'en laisser un actif. À ce jour, **aucun endpoint à nous
  n'existe** (les autres de la liste appartiennent à d'autres élèves : ne pas y toucher).
- Lancer un seul pipeline à la fois, depuis la racine du repo :
  `uv run --env-file .env python -m scripts.pipeline_runner`.
- Processus longs : `execute_command` avec `background: true` ; un `nohup ... &` meurt à la fin
  de la commande.
- Un déploiement d'endpoint peut échouer sur le quota `CustomModelServingCPUsPerProjectPerRegion`
  (CPU occupés par d'autres élèves). Essayer `n1-standard-4` plutôt que `n1-standard-8`, et
  déployer tôt avant la démo. Le déploiement dure 15 à 30 minutes.

Pièges déjà rencontrés (utiles pour la section « problèmes rencontrés » de la présentation) :
- **Données corrompues par Gemini** : 32 notes contenaient des caractères de contrôle ou
  invisibles ; filtrées par `has_corrupted_text`. Ce piège se détecte avec le module `csv`, pas
  avec pandas.
- **Quota Gemini** : la clé AI Studio gratuite est limitée à 20 requêtes par jour et par modèle,
  et `gemini-2.5-flash` n'est plus ouvert aux nouveaux utilisateurs. La génération a été faite
  via Vertex AI : `genai.Client(vertexai=True, project=..., location="global")` avec
  `gemini-3.5-flash`.
- **Hugging Face** : `huggingface_hub` se bloque en local (`.incomplete` à 0 octet) ; `curl` marche.
- **Langfuse** : il faut `langfuse>=3,<4` (la v5 n'a plus `start_as_current_generation`). Le
  serveur v4 est en mode events_only : utiliser `/api/public/v2/observations`, pas `/traces`.
  L'API publique ne crée ni évaluateurs ni widgets : ils se créent dans l'UI.
- **Endpoint** : déploiement échoué sur le quota CPU (voir ci-dessus).
- **Surapprentissage (cas Yoda)** : passer de 10 à 3 epochs a fait monter Rouge-L de 0,831 à
  0,861 et baisser `eval_loss` de 2,99 à 1,56.
- Mesure des tokens du jeu CRM : exemple complet médiane 301, p95 444, max 512 ; JSON de sortie
  58 à 92 tokens. D'où `max_length=640` et `max_new_tokens=160`.

Secrets : `.env` (ignoré par git) contient les identifiants GCP, la clé Gemini et les clés
Langfuse. Chaque personne doit remplir le sien à partir de `.env.example`. `GCP_ENDPOINT_ID`
dans `.env` est **obsolète** (l'endpoint a été supprimé).

## 6. Ce qu'il reste à faire (dans l'ordre)

1. **Accès au repo.** Le code est déjà poussé (voir §3). Vérifier que vous avez accès en
   écriture. Aucune PR n'est ouverte : décider avec l'utilisateur si une PR `crm-use-case` ->
   `main` est nécessaire à la fin (elle inclut aussi `session-4-deployment`). Le collaborateur
   `MathieuHS` (le prof) a été invité au repo.
2. **Terminer le pipeline `...20261112183827`** : lire les métriques d'évaluation et analyser les
   erreurs par style, longueur et présence d'un élément parasite (colonnes `style`, `length`,
   `distractor` du CSV). Garder les chiffres pour le brief.
3. **Enregistrer le modèle CRM** dans le registre :
   ```bash
   uv run --env-file .env python -m scripts.register_model_with_custom_handler \
       --model-uri gs://emeret-llmops/vertexai-pipeline-root/123905721265/model-training-pipeline-20261112183827/fine-tuning-component_9118750344375959552/model \
       --model-name emeret-ureboullet_model --parent-model 6374284521612771328
   ```
   `--parent-model` en fait la version 2 du modèle Yoda ; omettre cette option et choisir un
   nouveau nom pour un modèle séparé (plus clair, puisque le cas d'usage a changé : à décider).
4. **Déployer un endpoint** avec `scripts.deploy_endpoint --model <nom> --endpoint-name <nom>`,
   renseigner `GCP_ENDPOINT_ID` dans `.env`, tester avec `curl` (voir `README.md`) puis avec l'app :
   `PYTHONPATH=. uv run --env-file .env chainlit run src/app/main.py`.
   **Supprimer l'endpoint ensuite**, et le redéployer uniquement pour la démo.
5. **Langfuse** (UI, auto-hébergé via Docker Compose, voir `README.md`) : créer un évaluateur
   LLM-as-a-judge adapté au CRM (par exemple fidélité de la fiche à la note, ou hallucination de
   champs) et construire un dashboard : taux de JSON valide, `schema_valid`, `names_grounded`,
   latence. Le prompt « Yoda-ness » est obsolète. Le Langfuse existant tourne sur la machine
   d'Enzo (`http://localhost:3000`, projet `yoda-chatbot`) ; un autre poste doit monter le sien.
6. **Rédiger l'AI product brief** et préparer la démo en direct : cas d'usage et utilisateur
   visé, données (synthétiques, contrôle croisé, filtrage), modèle, métriques et résultats,
   coûts, limites, monitoring, problèmes rencontrés (§5).
7. **Questions à poser au prof** : le suivi d'expériences (Vertex AI Experiments) figure dans le
   plan du cours mais n'est couvert par aucune pratique ; consignes exactes de rendu et dates.
8. Mettre à jour `README.md` avec les résultats finaux et l'URL de la PR.

## 7. Fiabilité de ce document

Établi le 12/11/2026 à partir de l'état du dépôt et des API GCP. L'état du pipeline (§4) peut avoir
changé depuis : le relire avant d'agir. Les métriques d'évaluation du cas CRM ne sont **pas encore
connues** : ne pas en citer avant de les avoir lues.
