# =============================================================================
# Composant Kubeflow : préparation du dataset Yoda pour le fine-tuning de Phi-3
# =============================================================================
# Ce fichier définit UNE étape (un "composant") du pipeline Kubeflow.
# Le composant :
#   1. lit le CSV brut des phrases Yoda depuis le bucket GCS
#   2. le convertit en Dataset Hugging Face
#   3. met chaque ligne au format conversation (user -> assistant)
#   4. découpe les données en un jeu d'entraînement et un jeu de test
#   5. écrit les deux jeux de données en CSV
# =============================================================================

# OutputPath : sert à déclarer un fichier de sortie dont Kubeflow choisit le chemin.
# component  : le décorateur qui transforme une fonction Python en composant Kubeflow.
from kfp.dsl import OutputPath, component


# -----------------------------------------------------------------------------
# Le décorateur @component
# -----------------------------------------------------------------------------
# Dans le cloud, le composant tourne dans un conteneur Docker : une mini-machine
# isolée, créée juste pour lui.
#   - base_image : la machine de départ. Ici un Linux léger avec Python 3.11
#     (même version que notre .venv), maintenu par l'équipe Python sur Docker Hub.
#   - packages_to_install : les librairies à installer dans ce conteneur avant
#     de lancer la fonction. On fixe les versions (==) pour avoir exactement
#     les mêmes qu'en local : ce qui marche sur le Mac marchera dans le cloud.
@component(
    base_image="python:3.11-slim",
    packages_to_install=["pandas==3.0.6", "datasets==5.1.0", "gcsfs==2026.8.1"],
)
def transform_data(
    # Adresse du CSV d'entrée, par exemple "gs://emeret-llmops/yoda_sentences.csv".
    input_path: str,
    # Fichiers de sortie : on ne donne PAS ces chemins nous-mêmes.
    # Kubeflow les fournit au lancement, puis Vertex AI range les fichiers
    # dans le bucket et les affiche comme "artefacts" dans la console GCP.
    train_path: OutputPath("Dataset"),
    test_path: OutputPath("Dataset"),
    # Part des données réservée au test (0.2 = 20 %).
    test_size: float = 0.2,
    # Graine du hasard : même graine = même découpage à chaque lancement
    # (résultat reproductible pour toute l'équipe).
    seed: int = 42,
):
    # -------------------------------------------------------------------------
    # Imports
    # -------------------------------------------------------------------------
    # Les imports sont DANS la fonction : Kubeflow n'envoie dans le conteneur
    # que le code de cette fonction, pas le reste du fichier. Un import placé
    # en haut du fichier n'existerait donc pas dans le cloud.
    import json
    import logging

    import pandas as pd
    from datasets import Dataset

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    # On utilise logging plutôt que print : chaque message a l'heure et un
    # niveau (INFO, WARNING, ERROR), ce qui rend les logs lisibles dans la
    # console GCP quand on cherche pourquoi un pipeline a échoué.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    # -------------------------------------------------------------------------
    # Petites fonctions utilitaires
    # -------------------------------------------------------------------------
    # Elles sont aussi définies DANS le composant, pour la même raison que les imports.

    def to_conversation(example: dict) -> dict:
        # Reçoit UNE ligne du dataset sous forme de dictionnaire :
        #   {"sentence": ..., "translation": ..., "translation_extra": ...}
        # et renvoie une conversation au format attendu par SFTTrainer :
        #   - "user"      : la phrase normale
        #   - "assistant" : la même phrase dite par Yoda (version avec "Yes, hrrrm")
        return {
            "messages": [
                {"role": "user", "content": example["sentence"]},
                {"role": "assistant", "content": example["translation_extra"]},
            ]
        }

    def to_json(example: dict) -> dict:
        # Convertit la liste de messages en texte JSON.
        # Sans ça, le CSV contiendrait un format interne illisible (numpy),
        # impossible à relire au moment de l'entraînement.
        return {"messages": json.dumps(example["messages"])}

    # -------------------------------------------------------------------------
    # Étape 1 : lire le CSV depuis le bucket GCS
    # -------------------------------------------------------------------------
    # pandas lit directement une adresse "gs://" grâce à la librairie gcsfs.
    # Résultat : un DataFrame (un tableau) de 720 lignes et 3 colonnes :
    # sentence, translation, translation_extra.
    logger.info(f"Lecture du fichier {input_path}")
    df = pd.read_csv(input_path)
    logger.info(f"Nombre de lignes et de colonnes : {df.shape}")

    # -------------------------------------------------------------------------
    # Étape 2 : convertir le DataFrame pandas en Dataset Hugging Face
    # -------------------------------------------------------------------------
    # SFTTrainer (l'outil de fine-tuning de Hugging Face) attend un Dataset,
    # pas un DataFrame. Le Dataset offre aussi .map() et .train_test_split().
    # Dans un Dataset, chaque ligne est un dictionnaire {"colonne": valeur}.
    dataset = Dataset.from_pandas(df)

    # -------------------------------------------------------------------------
    # Étape 3 : mettre au format conversation
    # -------------------------------------------------------------------------
    # .map() applique to_conversation à chacune des 720 lignes.
    # remove_columns supprime les 3 anciennes colonnes : il ne reste que "messages".
    dataset = dataset.map(to_conversation, remove_columns=dataset.column_names)
    logger.info(f"Exemple de conversation : {dataset[0]['messages']}")

    # -------------------------------------------------------------------------
    # Étape 4 : découper en jeu d'entraînement et jeu de test
    # -------------------------------------------------------------------------
    # train (80 %, 576 lignes) : les exemples sur lesquels le modèle apprend.
    # test  (20 %, 144 lignes) : jamais vus pendant l'entraînement, servent à
    # vérifier que le modèle a vraiment appris et pas juste appris par cœur.
    # train_test_split renvoie un DatasetDict : un dictionnaire de 2 Datasets.
    split = dataset.train_test_split(test_size=test_size, seed=seed)
    train_dataset = split["train"]
    test_dataset = split["test"]
    logger.info(f"Train : {len(train_dataset)} lignes, test : {len(test_dataset)} lignes")

    # -------------------------------------------------------------------------
    # Étape 5 : écrire les deux jeux de données en CSV
    # -------------------------------------------------------------------------
    # On convertit d'abord chaque conversation en texte JSON (to_json), puis on
    # écrit le CSV aux chemins fournis par Kubeflow (ou par nous en local).
    # index=False : on n'écrit pas la colonne de numéros de ligne.
    train_dataset.map(to_json).to_csv(train_path, index=False)
    test_dataset.map(to_json).to_csv(test_path, index=False)
    logger.info(f"Fichiers écrits : {train_path}, {test_path}")


# -----------------------------------------------------------------------------
# Test en local
# -----------------------------------------------------------------------------
# Ce bloc ne s'exécute que si on lance ce fichier directement :
#   uv run python src/pipeline_components/data_transformation_component.py
# Il ne s'exécute PAS quand le pipeline importe le composant.
# Une fois décorée par @component, la fonction n'est plus appelable directement :
# .python_func donne accès à la fonction Python d'origine, sans Kubeflow.
# En local, c'est nous qui choisissons où écrire les fichiers de sortie.
if __name__ == "__main__":
    transform_data.python_func(
        input_path="gs://emeret-llmops/yoda_sentences.csv",
        train_path="../data/yoda_train.csv",
        test_path="../data/yoda_test.csv",
    )
