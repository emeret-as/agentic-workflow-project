## Ce qui est tracé
Chaque fiche remplie crée une trace `User Message`, que la note vienne de l'app Chainlit ou de cette démo Streamlit. Elle garde les notes en entrée et la fiche en sortie. À l'intérieur, une generation `Vertex AI endpoint` garde :
- la requête envoyée (prompt et paramètres de génération) ;
- la réponse brute ;
- le modèle, sa version et le temps de réponse.

Une panne de l'endpoint y est marquée `ERROR`.

## Les scores
| Score | Rempli par | Ce qu'il mesure |
|---|---|---|
| `json_valid` | le code, à chaque appel | la réponse contient un JSON lisible |
| `schema_valid` | le code, à chaque appel | les 7 champs, les bons types, les listes fermées |
| `names_grounded` | le code, à chaque appel | l'entreprise et le contact se retrouvent dans les notes |
| `fidelite_fiche` | un juge LLM (Gemini), dans Langfuse | la fiche est fidèle aux notes : 1, 0,5 ou 0, avec une justification |
| `exact_match` | le script d'envoi des notes de test | les 7 champs égaux à la référence (jeu de test seulement) |
| `avis_utilisateur`, `champs_corriges` | le commercial, dans la démo | pouce levé ou baissé ; nombre de champs modifiés avant validation |

## Ce que le monitoring a déjà attrapé
Les 56 notes de test et 7 notes pièges, écrites à la main, ont été envoyées à l'endpoint.

Sur les notes pièges :
- **La recette de cuisine** a reçu une fiche « valide », mais inventée de bout en bout (« Clinique Valmont », « Sophie Bernard »). Seul `names_grounded` passe à 0 : la forme est bonne, le fond est faux. C'est pour ce cas que le juge LLM existe.
- **Le besoin hors liste** (refaire un site vitrine) a produit une catégorie inventée, `website_redesign`. Le garde-fou bloque la fiche (`schema_valid` = 0).
- **La note en anglais** passe les contrôles, mais le budget de 80 k£ est converti en 72 000 € sans que la note le dise.

## Limite du juge
Les notes d'entraînement viennent de Gemini, et le juge est aussi un Gemini : ils peuvent partager les mêmes angles morts. Pour cette raison, les exemples du prompt du juge sont écrits à la main.
