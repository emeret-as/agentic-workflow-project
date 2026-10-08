import json

import pandas as pd
from datasets import Dataset


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


def transform_data(input_path: str, train_path: str, test_path: str):
    # Lecture du CSV directement depuis le bucket GCS
    df = pd.read_csv(input_path)
    print(f"Nombre de lignes et de colonnes : {df.shape}")

    # Conversion du DataFrame pandas en Dataset Hugging Face
    dataset = Dataset.from_pandas(df)

    # Mise au format conversationnel attendu par SFTTrainer
    dataset = dataset.map(to_conversation, remove_columns=dataset.column_names)

    # Découpage en jeu d'entraînement (80 %) et de test (20 %)
    split = dataset.train_test_split(test_size=0.2, seed=42)
    train_dataset = split["train"]
    test_dataset = split["test"]
    print(f"Train : {len(train_dataset)} lignes")
    print(f"Test  : {len(test_dataset)} lignes")

    # Écriture des deux jeux de données en CSV
    # La conversation est convertie en texte JSON pour pouvoir être relue ensuite
    train_dataset = train_dataset.map(to_json)
    test_dataset = test_dataset.map(to_json)
    train_dataset.to_csv(train_path, index=False)
    test_dataset.to_csv(test_path, index=False)
    print(f"Fichiers écrits : {train_path}, {test_path}")


if __name__ == "__main__":
    transform_data(
        input_path="gs://emeret-llmops/yoda_sentences.csv",
        train_path="../data/yoda_train.csv",
        test_path="../data/yoda_test.csv",
    )
