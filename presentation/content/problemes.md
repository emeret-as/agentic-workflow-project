| Problème | Ce qu'on a changé |
|---|---|
| Le sujet du TP (traduire en langage de Yoda) n'était pas notre cas d'usage | Changement pour notes de réunion → fiche CRM. On a gardé tout le pipeline du cours, en changeant les données, le prompt et les métriques. |
| Aucun jeu de données public ne correspond (les jeux « texte → JSON » trouvés sont génériques, et leurs fiches contiennent des inventions) | Données synthétiques : on tire d'abord la fiche, puis Gemini rédige la note. Une seconde extraction contrôle chaque note : 558 notes gardées. |
| Clé Gemini gratuite limitée à 20 requêtes par jour | Génération via Gemini sur Vertex AI, dans notre projet GCP, pour quelques centimes |
| 32 notes générées contenaient des caractères invisibles | Filtre `has_corrupted_text` avant l'entraînement |
| 13 notes ont des « é » remplacés par des tabulations : le filtre autorise la tabulation, elles sont passées | Repéré à l'analyse des erreurs. C'est la seule note ratée par le pipeline. Le filtre est à corriger avant le prochain entraînement. |
| Surapprentissage au TP Yoda : la perte de validation remontait après 2 epochs | 3 epochs au lieu de 10 (Rouge-L de 0,831 à 0,861) |
| Longueur des sorties : la fiche fait 58 à 92 tokens, et les exemples complets jusqu'à 512 | `max_length` 640 à l'entraînement, `max_new_tokens` 160 au service |
| Déploiement de l'endpoint refusé : quota de CPU partagé avec les autres équipes | Machine `n1-standard-4` au lieu de `n1-standard-8`, avec un script qui déploie et supprime l'endpoint |
| Langfuse v4 refuse les anciennes routes de lecture (`/traces`, `/scores`) | Lecture par `/api/public/v2/observations` et `/api/public/v3/scores`. SDK gardé en v3 : la v5 n'a plus `start_as_current_generation`. |
| Port 5432 déjà pris par un Postgres local, Docker limité à 4 Go | Postgres de Langfuse exposé sur 5433 (`docker-compose.override.yml`) ; Langfuse occupe environ 2,4 Go |
| Écart entre le pipeline (55/56 fiches exactes) et l'endpoint (56/56) | Le pipeline charge Phi-3 en 4 bits, l'endpoint en float16 : la quantification coûte une fiche. À garder en tête avant de comparer deux chiffres. |
