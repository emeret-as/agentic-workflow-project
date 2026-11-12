"""Data transformation component for Vertex AI pipeline."""

from kfp.dsl import OutputPath, component


@component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "pandas==3.0.6",
        "datasets==5.1.0",
        "gcsfs==2026.8.1",
        "fsspec==2026.7.0",
    ],
)
def data_transformation_component(
    raw_dataset_uri: str,
    train_test_split_ratio: float,
    train_dataset: OutputPath("Dataset"),  # type: ignore
    test_dataset: OutputPath("Dataset"),  # type: ignore
) -> None:
    """Format and split CRM meeting notes for Phi-3 fine-tuning."""
    import logging

    import pandas as pd
    from datasets import Dataset

    # Consigne placée devant les notes. Copie de `src/crm_schema.py` (un
    # composant Kubeflow est autonome) : la garder identique au mot près, y
    # compris dans l'inférence, le handler et l'app.
    instruction = (
        "Extrais la fiche CRM au format JSON à partir des notes de réunion "
        "ci-dessous. Clés : company, contact_name, contact_role, need, "
        "budget_eur, next_action, deadline. Utilise null quand l'information "
        "est absente.\n\n"
    )

    def format_dataset_to_phi_messages(dataset: Dataset) -> Dataset:
        """Format dataset to Phi messages structure."""

        def format_dataset(examples):
            """Format a single example to Phi messages structure."""
            converted_sample = [
                {"role": "user", "content": instruction + examples["note"]},
                {"role": "assistant", "content": examples["record"]},
            ]
            return {"messages": converted_sample}

        # On garde le style, la longueur et l'élément parasite : ils servent à
        # analyser les erreurs par catégorie, ils ne sont pas utilisés pour
        # l'entraînement (SFTTrainer ne lit que `messages`).
        return dataset.map(format_dataset).remove_columns(["note", "record"])

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting data transformation process...")

    logger.info(f"Reading from {raw_dataset_uri}")
    dataset = Dataset.from_pandas(pd.read_csv(raw_dataset_uri))

    logger.info("Formatting and splitting dataset...")
    formatted_dataset = format_dataset_to_phi_messages(dataset)
    split_dataset = formatted_dataset.train_test_split(
        test_size=train_test_split_ratio, seed=42
    )
    logger.info(
        f"Train: {len(split_dataset['train'])} rows, "
        f"test: {len(split_dataset['test'])} rows"
    )

    logger.info(f"Writing train dataset to {train_dataset}...")
    split_dataset["train"].to_csv(train_dataset, index=False)

    logger.info(f"Writing test dataset to {test_dataset}...")
    split_dataset["test"].to_csv(test_dataset, index=False)

    logger.info("Data transformation process completed successfully")
