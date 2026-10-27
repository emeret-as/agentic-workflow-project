# =============================================================================
# Pipeline Kubeflow : entraînement du modèle Yoda
# =============================================================================
# Un pipeline est une chaîne d'étapes (de composants) qui s'enchaînent
# automatiquement. Pour l'instant il n'y a qu'une étape : la préparation des
# données. Plus tard, on ajoutera l'entraînement et l'évaluation de Phi-3.
#
# Ce fichier ne lance rien tout seul : il DÉCRIT le pipeline. C'est le script
# runner (scripts/pipeline_runner.py) qui le compile en fichier YAML (la
# "recette" que Vertex AI sait lire) puis l'envoie sur Vertex AI.
# =============================================================================

# pipeline : le décorateur qui transforme une fonction Python en pipeline Kubeflow.
from kfp.dsl import pipeline

# On importe le composant de préparation des données.
# "src." fonctionne quand on lance les scripts depuis la racine du projet
# (le dossier agentic-workflow-project/).
from src.pipeline_components.data_transformation_component import transform_data


# -----------------------------------------------------------------------------
# Le décorateur @pipeline
# -----------------------------------------------------------------------------
#   - name        : le nom affiché dans la console Vertex AI.
#   - description : une phrase qui explique à quoi sert le pipeline.
@pipeline(
    name="model-training-pipeline",
    description="Prépare le dataset Yoda pour le fine-tuning de Phi-3",
)
def model_training_pipeline(
    # Paramètres du pipeline : on peut les changer au lancement, sans toucher
    # au code. Les valeurs après "=" sont celles utilisées par défaut.
    # Adresse du CSV brut dans notre bucket.
    input_path: str = "gs://emeret-llmops/yoda_sentences.csv",
    # Part des données réservée au test (20 %).
    test_size: float = 0.2,
    # Graine du hasard, pour un découpage identique à chaque lancement.
    seed: int = 42,
):
    # Étape unique : lecture, mise au format conversation et découpage train/test.
    # On transmet les paramètres du pipeline au composant.
    # On ne donne PAS train_path ni test_path : ce sont des OutputPath,
    # Kubeflow les crée lui-même et les range dans le bucket (pipeline_root).
    transform_data(input_path=input_path, test_size=test_size, seed=seed)
