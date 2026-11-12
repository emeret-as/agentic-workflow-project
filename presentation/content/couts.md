## Ce que ça coûte
Prix Vertex AI à Londres (europe-west2), vérifiés le 12/11/2026. Le prof demande de rester bien en dessous de 50 $.

| Ressource | Machine | Prix |
|---|---|---|
| Étapes GPU du pipeline (fine-tuning, inférence) | n1-standard-16 + 1 GPU T4 | ≈ 1,60 $ / h |
| Étapes sans GPU (données, évaluation) | e2-standard-4 | quelques centimes |
| Endpoint | n1-standard-4 + 1 GPU T4 | moins de 1,03 $ / h (prix de n1-standard-8 + T4) |

## Dépenses du cas CRM
Durées facturées lues dans Vertex AI. Le coût est estimé avec les prix ci-dessus : l'API de facturation est désactivée sur le projet partagé du cours.

| Dépense | Durée facturée | Coût estimé |
|---|---|---|
| Génération des notes (Gemini sur Vertex AI) | une fois | quelques centimes |
| Fine-tuning (pipeline du 12/11) | 79 min | ≈ 2,10 $ |
| Inférence sur le jeu de test (même pipeline) | 10 min | ≈ 0,30 $ |
| Évaluation de Phi-3 de base (second pipeline) | moins de 30 min | ≈ 0,50 $ au plus |
| Endpoint : déploiement, 63 notes de test, démo Chainlit et Streamlit, puis suppression | 32 min | ≈ 0,55 $ au plus |
| **Total** | | **≈ 3,50 $** |

L'endpoint n'a pas de mise en veille : il facture tant qu'il existe, jusqu'à environ 25 $ par jour. Il est supprimé après chaque usage par `scripts/deploy_endpoint.py --delete`, et redéployé environ 30 minutes avant la démo.
