# =============================================================================
# Test local de l'évaluation (session 3, partie 3)
# =============================================================================
# On écrit le code morceau par morceau avant de le mettre dans un composant
# Kubeflow.
# À lancer depuis la racine du projet :
#   uv run python -W ignore local_tests/evaluation_test.py
# =============================================================================

import pandas as pd
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics import ExactMatch, NonLLMStringSimilarity, RougeScore
from ragas.metrics.base import SingleTurnMetric

# CSV produit par l'étape d'inférence, téléchargé depuis le bucket
PREDICTIONS_PATH = "outputs/predictions.csv"

# -----------------------------------------------------------------------------
# 1. Chargement des prédictions
# -----------------------------------------------------------------------------
predictions = pd.read_csv(PREDICTIONS_PATH)

print(f"{len(predictions)} prédictions, colonnes : {list(predictions.columns)}")
print(predictions.head(3).to_string())

# -----------------------------------------------------------------------------
# 2. Les métriques (sans LLM) : chacune compare la réponse du modèle à la
#    vraie phrase Yoda et donne un score entre 0 (rien à voir) et 1 (identique)
# -----------------------------------------------------------------------------
metric_definitions = [
    RougeScore(rouge_type="rougeL", mode="fmeasure"),  # plus longue suite de mots en commun
    # Pas de BleuScore : dans ragas 0.4.3 il ne compare que la 1re phrase
    # de la réponse (ex. 1,0 pour deux phrases différentes)
    NonLLMStringSimilarity(),  # nombre de lettres à changer (distance de Levenshtein)
    ExactMatch(),  # 1 si les deux phrases sont exactement identiques, sinon 0
]
print("\nMétriques :", [metric.name for metric in metric_definitions])


# -----------------------------------------------------------------------------
# 3. compute_metrics : une prédiction -> un score par métrique
# -----------------------------------------------------------------------------
def compute_metrics(
    user_input: str,
    response: str,
    reference: str,
    metric_definitions: list[SingleTurnMetric],
) -> dict[str, float | int]:
    """Compute metrics for a single prediction."""
    # SingleTurnSample : le format de ragas pour un échange question -> réponse
    sample = SingleTurnSample(
        user_input=user_input,  # la phrase normale
        response=response,  # la réponse du modèle
        reference=reference,  # la vraie phrase Yoda
    )
    return {metric.name: metric.single_turn_score(sample) for metric in metric_definitions}


# -----------------------------------------------------------------------------
# 4. Boucle sur toutes les prédictions -> tableau des scores par phrase
# -----------------------------------------------------------------------------
# Une réponse vide est lue comme NaN par pandas : on la remplace par ""
predictions["extracted_response"] = predictions["extracted_response"].fillna("")

results = []
for row in predictions.itertuples():
    scores = compute_metrics(
        row.user_input, row.extracted_response, row.reference, metric_definitions
    )
    # On garde les phrases à côté des scores pour pouvoir relire le tableau
    results.append(
        {
            "user_input": row.user_input,
            "reference": row.reference,
            "extracted_response": row.extracted_response,
            **scores,
        }
    )
per_sample_metrics = pd.DataFrame(results)

print(f"\nScores par phrase : {per_sample_metrics.shape[0]} lignes")
print(per_sample_metrics[[metric.name for metric in metric_definitions]].head().to_string())


# -----------------------------------------------------------------------------
# 5. aggregate_metrics : scores par phrase -> un score global par métrique
# -----------------------------------------------------------------------------
def aggregate_metrics(per_sample_metrics: pd.DataFrame) -> dict[str, float]:
    """Aggregate metrics from per-sample metrics DataFrame."""
    # Moyenne de chaque colonne de scores (les colonnes de texte sont ignorées)
    means = per_sample_metrics.select_dtypes("number").mean()
    return {f"{name}_mean": float(value) for name, value in means.items()}


print("\nScores globaux :")
for name, value in aggregate_metrics(per_sample_metrics).items():
    print(f"  {name} = {value:.3f}")
