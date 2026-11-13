# Passation du projet Agentic Workflow (LLMOps)

Document destiné à un assistant de codage agentique qui reprend le projet. Il décrit l'objectif,
l'état au 13/11/2026 (sessions 1 à 6 terminées côté code), les pièges déjà rencontrés et ce qu'il
reste à faire avant l'oral.
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
(`company`, `contact_name`, `contact_role`, `need`, `budget_eur`, `next_action`, `deadline`).
`need` (8 valeurs) et `next_action` (6 valeurs) sont des listes fermées ; un champ absent de la
note vaut `null`. Modèle : `microsoft/Phi-3-mini-4k-instruct` fine-tuné en LoRA. Données 100 %
synthétiques (Gemini).

Évaluation en deux temps :
- **Pipeline** : métriques déterministes, sans LLM juge (JSON valide, schéma valide, exactitude par
  champ, fiche exacte, champ inventé), comparées à Phi-3 de base sur les mêmes 56 notes de test.
- **Monitoring** : score de fidélité `fidelite_fiche` donné par un juge LLM (Gemini sur Vertex AI,
  `src/llm_judge.py`), en direct dans la démo et sur les traces Langfuse.

## 2. Infrastructure

| Élément | Valeur |
|---|---|
| Projet GCP | `agentics-workflows-510809` (numéro `123905721265`) |
| Région | `europe-west2` (seule région avec quota GPU) |
| Bucket | `emeret-llmops` |
| Repo GitHub | https://github.com/emeret-as/agentic-workflow-project |
| Branche de référence | `main` (les PR #2 `crm-use-case` et #3 `session-4-crm` sont fusionnées) |
| Modèle CRM dans le registre | `emeret-crm-phi3` v1, `models/645705795597500416` |
| Ancien modèle Yoda | `models/6374284521612771328` (`emeret-ureboullet_model`), plus utilisé |

Données : `data/crm_meeting_notes.csv` (558 notes, versionné), copie sur
`gs://emeret-llmops/crm_meeting_notes.csv` (`RAW_DATASET_URI` dans `src/constants.py`).

## 3. État du code (branche `main`)

Tout est fusionné dans `main` : pipeline CRM, déploiement, Langfuse, app de présentation. Récupérer
le travail avec `git fetch && git checkout main && git pull`.

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
- Tests locaux (sans GCP) : `local_tests/crm_metrics_test.py`, `local_tests/crm_app_test.py`,
  `presentation/tests/test_crm.py`.
- `src/llm_judge.py` : juge LLM de fidélité (Gemini sur Vertex AI). Scripts associés :
  `scripts/run_llm_judge.py`, `scripts/send_test_notes.py`, `scripts/create_langfuse_dashboard.py`.
- `scripts/base_model_evaluation_runner.py` et `scripts/build_results.py` : évaluation de Phi-3 de
  base et collecte des résultats des deux pipelines dans `presentation/data/results.json`.
- `presentation/` : app Streamlit de la soutenance (7 pages, mode « Recorded replay ») et
  `presentation/speech.md`, le texte de l'oral (10 minutes, en anglais).

Validation (tout passe à ce jour) :
```bash
PYTHONPATH=. uv run --env-file .env python local_tests/crm_app_test.py
PYTHONPATH=. uv run --env-file .env python local_tests/crm_metrics_test.py
uvx ruff check . && uvx ruff format --check src scripts local_tests/crm_*.py
```
`ruff format --check .` signale 2 anciens fichiers de tests Yoda (`local_tests/evaluation_test.py`
et un autre) : ils ne sont pas à nous, ne pas les reformater.

## 4. Avancement par session (au 13/11)

| Session | État |
|---|---|
| 1-3 Données, pipeline | **Fait.** Run `model-training-pipeline-20261112183827` réussi. Sur 56 notes de test : JSON 100 %, schéma 100 %, fiche exacte 98,2 %, champ inventé 1,8 %. |
| Référence Phi-3 de base | Pipeline `base_model_evaluation_pipeline` (même test, même évaluation, `use_base_model=True`), run `base-model-evaluation-pipeline-20261112212113`. |
| 4 Registre, endpoint, app | **Fait.** Modèle `emeret-crm-phi3` v1 (`models/645705795597500416`). Endpoint déployé en `n1-standard-4` + T4, testé avec curl, l'app Chainlit et l'app Streamlit, puis **supprimé**. Sur l'endpoint (float16) : 56/56 fiches exactes, environ 5,5 s par note. |
| 5 Langfuse | **Fait.** Langfuse v4 auto-hébergé dans `../langfuse`, projet `crm-notes`. 63 traces : 56 notes de test et 7 notes pièges, via `scripts/send_test_notes.py`. Dashboard créé par `scripts/create_langfuse_dashboard.py`. Juge LLM `fidelite_fiche` (`src/llm_judge.py`) : Gemini sur Vertex AI, en direct dans la démo, et `scripts/run_llm_judge.py` pour les traces passées. |
| 6 Présentation | App Streamlit dans `presentation/`, 7 pages, adaptée au schéma CRM. Mode rejeu sur de vraies réponses de l'endpoint. |

Pièges trouvés le 12/11 au soir :
- 13 notes ont des « é » remplacés par des tabulations (17 notes contiennent une tabulation, dont 13
  au milieu d'un mot) : `has_corrupted_text` autorise `\t`. **Non corrigé** : ces notes sont dans
  les données d'entraînement.
- Le pipeline (Phi-3 en 4 bits) rate une fiche que l'endpoint (float16) réussit.
- Port 5432 pris sur le Mac d'Ugo : Postgres de Langfuse exposé sur 5433 (`docker-compose.override.yml`).
- `gsutil` et `gcloud logging` demandent une ré-authentification ; le SDK Python (ADC) marche.

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

## 6. Ce qu'il reste à faire (état au 13/11)

Fait : juge LLM (Gemini sur Vertex AI, car la connexion « Google AI Studio » de Langfuse échouait
avec une clé gratuite), page Monitoring qui lit les chiffres en direct dans Langfuse, résultats
Phi-3 de base vs fine-tuné, texte de l'oral.

À faire :
1. **Corriger `has_corrupted_text`** (tabulations au milieu d'un mot) avant tout nouvel entraînement.
   Sinon, le dire tel quel à l'oral, sans le présenter comme réglé.
2. **Vérifier une affirmation de l'oral** : `presentation/speech.md` (section 6) dit que la note
   ratée par le pipeline est « exactement » une des notes à tabulation. Ce lien n'a pas été vérifié.
3. **Chiffrer le coût réel** (entraînement de 79 minutes sur T4, endpoints, Gemini) : l'oral n'en
   donne aucun et le budget indicatif est de 50 $.
4. **Jour de la démo** : redéployer l'endpoint 30 minutes avant
   (`scripts.deploy_endpoint --machine-type n1-standard-4`), renseigner `GCP_ENDPOINT_ID` dans
   `.env`, puis le supprimer juste après. Prévoir le mode « Recorded replay » comme secours et
   l'annoncer comme tel.
5. **Questions au prof** : suivi d'expériences (Vertex AI Experiments) et consignes exactes de rendu.
6. **Limites à assumer à l'oral** : 98 % vient de 56 notes synthétiques générées comme
   l'entraînement, sans vraie note de commercial ; la détection de dérive repose sur des courbes
   Langfuse sans seuil d'alerte.

Langfuse tourne sur le Mac d'Ugo (`../langfuse`, Docker). Le compte `admin@emeret.local` et son
mot de passe sont dans `../langfuse/.env`, jamais commités. Un autre poste doit monter son propre
Langfuse (voir le README).

## 7. Fiabilité de ce document

Mis à jour le 13/11/2026 après relecture du dépôt `main` (commit `536a31a`). Les chiffres de la
section 4 (56 notes de test) viennent de `presentation/data/results.json`, produit par
`scripts/build_results.py` à partir des runs `model-training-pipeline-20261112183827` et
`base-model-evaluation-pipeline-20261112212113`. Ils n'ont pas été relus directement dans Vertex AI.
L'état des endpoints et de Langfuse peut avoir changé : le relire avant d'agir.
