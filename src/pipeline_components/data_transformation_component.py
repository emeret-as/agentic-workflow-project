from kfp.dsl import OutputPath, component


@component(
    base_image="python:3.11-slim",
    packages_to_install=["pandas==3.0.6", "datasets==5.1.0", "gcsfs==2026.8.1"],
)
def transform_data(
    input_path: str,
    train_path: OutputPath("Dataset"),
    test_path: OutputPath("Dataset"),
    test_size: float = 0.2,
    seed: int = 42,
):
    # Les imports sont dans la fonction : le composant tourne seul dans son conteneur
    import json
    import logging

    import pandas as pd
    from datasets import Dataset

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

    def to_conversation(example: dict) -> dict:
        # Transforme une ligne en conversation user -> assistant
        return {
            "messages": [
                {"role": "user", "content": example["sentence"]},
                {"role": "assistant", "content": example["translation_extra"]},
            ]
        }

    def to_json(example: dict) -> dict:
        # Convertit la liste de messages en texte JSON
        return {"messages": json.dumps(example["messages"])}

    # Lecture du CSV directement depuis le bucket GCS
    logger.info(f"Lecture du fichier {input_path}")
    df = pd.read_csv(input_path)
    logger.info(f"Nombre de lignes et de colonnes : {df.shape}")

    # Conversion du DataFrame pandas en Dataset Hugging Face
    dataset = Dataset.from_pandas(df)

    # Mise au format conversationnel attendu par SFTTrainer
    dataset = dataset.map(to_conversation, remove_columns=dataset.column_names)
    logger.info(f"Exemple de conversation : {dataset[0]['messages']}")

    # Découpage en jeu d'entraînement et de test
    split = dataset.train_test_split(test_size=test_size, seed=seed)
    train_dataset = split["train"]
    test_dataset = split["test"]
    logger.info(f"Train : {len(train_dataset)} lignes, test : {len(test_dataset)} lignes")

    # Écriture des deux jeux de données en CSV
    # La conversation est convertie en texte JSON pour pouvoir être relue ensuite
    train_dataset.map(to_json).to_csv(train_path, index=False)
    test_dataset.map(to_json).to_csv(test_path, index=False)
    logger.info(f"Fichiers écrits : {train_path}, {test_path}")


if __name__ == "__main__":
    # Test en local : python_func appelle la fonction Python d'origine, sans Kubeflow
    transform_data.python_func(
        input_path="gs://emeret-llmops/yoda_sentences.csv",
        train_path="../data/yoda_train.csv",
        test_path="../data/yoda_test.csv",
    )
