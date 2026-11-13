# Évaluateur LLM-as-a-judge Langfuse : « fidelite_fiche »

Juge LLM de la session 5, à la place du critique « Yoda-ness » du cours. Il tourne sur chaque
fiche de la démo (`src/llm_judge.py`), et `scripts/run_llm_judge.py` note les traces passées.

Il appelle Gemini par Vertex AI, et non par la connexion LLM de l'interface Langfuse prévue
au TP. Avec une clé Gemini gratuite, cette connexion échouait : `gemini-2.5-flash` est fermé
aux nouveaux comptes, et les modèles plus récents étaient saturés.

- **Nom du score** : `fidelite_fiche`
- **Variables** : `{{input}}` = input de la trace (note brute), `{{output}}` = output de
  la trace (fiche JSON extraite)
- **Pourquoi ce juge** : les scores automatiques de l'app (`json_valid`, `schema_valid`,
  `names_grounded`) vérifient la forme et les noms propres, mais pas le sens. Ils ne voient
  pas un besoin mal classé, une échéance inventée à partir d'une date parasite, ni un
  budget mal converti. C'est l'erreur restante du modèle sur le jeu de test (date
  d'un séminaire prise pour l'échéance). Les deux exemples du prompt sont inventés,
  aucun ne vient du jeu de test.

## Prompt

```text
Tu es un contrôleur qualité pour un CRM. Un modèle a transformé les notes de réunion d'un commercial en une fiche CRM JSON. Tu dois dire si la fiche est fidèle aux notes.

Règles de la fiche :
- company : nom de l'entreprise cliente ; contact_name / contact_role : l'interlocuteur et sa fonction, null si absents.
- need : une valeur parmi crm_migration, data_platform, cybersecurity, cloud_migration, ai_assistant, process_automation, analytics_dashboard, team_training.
- next_action : une valeur parmi send_proposal, schedule_demo, send_documentation, schedule_followup_call, involve_stakeholder, internal_review.
- budget_eur : montant en euros (entier), null si absent. deadline : date d'échéance du projet (AAAA-MM-JJ), null si absente.
- Une date ou un chiffre qui ne concerne pas le projet (séminaire, congés, taille de l'équipe, budget d'un concurrent) ne doit PAS être repris.

Barème :
- 1 : tous les champs sont justifiés par les notes, rien d'inventé, rien d'important oublié.
- 0.5 : un défaut mineur (fonction approximative, catégorie discutable entre deux valeurs proches).
- 0 : au moins une valeur inventée ou fausse (entreprise, contact, budget, échéance), ou une information importante des notes manquante, ou une sortie qui n'est pas une fiche.

Exemple 1
Notes : "Appel avec Camille Roux, DSI de la Clinique Duchêne. Ils veulent migrer leur CRM, budget 124 k€, à livrer pour le 26/02/2027. On invite leur sponsor au prochain échange."
Fiche : {"company": "Clinique Duchêne", "contact_name": "Camille Roux", "contact_role": "DSI", "need": "crm_migration", "budget_eur": 124000, "next_action": "involve_stakeholder", "deadline": "2027-02-26"}
Score : 1 (tout est dans les notes).

Exemple 2
Notes : "Point avec Marc Delorme, directeur commercial de Haudry Logistique : ils veulent un assistant IA interne, budget 60 k€, ils attendent l'accord de leur comité. Attention, Marc est en congés du 3 au 14 mars."
Fiche : {"company": "Haudry Logistique", "contact_name": "Marc Delorme", "contact_role": "directeur commercial", "need": "ai_assistant", "budget_eur": 60000, "next_action": "internal_review", "deadline": "2027-03-14"}
Score : 0 (la fin des congés n'est pas une échéance du projet : deadline devait être null).

Notes à évaluer :
{{input}}

Fiche produite par le modèle :
{{output}}

Donne d'abord ton raisonnement en une ou deux phrases, puis le score.
```

## Réglages

- Score : numérique, 1, 0,5 ou 0. La justification est enregistrée comme commentaire du score.
- Cible : les traces `User Message` dont la fiche passe le garde-fou.
- Modèle : `gemini-3.5-flash` sur Vertex AI, température 0, réponse en JSON.
