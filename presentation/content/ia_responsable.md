## Qui garde la main
| Règle | En pratique |
|---|---|
| Validation humaine | aucune fiche n'est enregistrée sans « Valider la fiche » ; avant, elle porte le tampon « Brouillon IA » |
| Garde-fou | une réponse qui n'est pas un JSON conforme (types, listes fermées) n'est jamais affichée comme une fiche |
| Champs vérifiés | l'entreprise, l'interlocuteur, la fonction, le budget et l'échéance sont recherchés dans les notes ; absents, ils sont signalés « à vérifier » |
| Vie privée | les notes passent en clair dans Langfuse, qui est auto-hébergé et ne quitte pas la machine. La démo n'utilise que des sociétés et des personnes fictives. En production, il faudrait masquer les noms avant l'envoi. |
| Biais | les données d'entraînement et le juge LLM sont de la même famille (Gemini). On teste aussi sur des notes pièges écrites à la main. |
