"""Fine-tuning component for Vertex AI pipeline."""

from kfp.dsl import Dataset, Input, Metrics, Model, Output, component


@component(
    # Image avec torch et les drivers GPU (CUDA) déjà installés
    base_image="pytorch/pytorch:2.8.0-cuda12.9-cudnn9-devel",
    # Versions exactes (leçon de la session 2) ; torch vient déjà de l'image
    packages_to_install=[
        "transformers==4.46.3",
        "peft==0.13.2",
        "trl==0.17.0",
        "accelerate==1.15.0",
        "datasets==4.8.5",
        "huggingface-hub==0.36.2",
        "bitsandbytes==0.48.2",
        "tensorboard==2.21.0",
    ],
)
def fine_tuning_component(
    train_dataset: Input[Dataset],
    model: Output[Model],
    metrics: Output[Metrics],
    base_model_id: str = "microsoft/Phi-3-mini-4k-instruct",
    validation_split_ratio: float = 0.1,
    lora_r: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    num_train_epochs: int = 10,
    learning_rate: float = 3e-4,
    per_device_train_batch_size: int = 16,
    max_length: int = 64,
) -> None:
    """Fine-tune Phi-3 on the Yoda dataset with LoRA."""
    import ast
    import logging
    import re

    import torch
    from datasets import Dataset as HFDataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting fine-tuning process...")

    # Hyper-paramètres clés, enregistrés avec les métriques
    hyperparameters = {
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "num_train_epochs": num_train_epochs,
        "learning_rate": learning_rate,
        "per_device_train_batch_size": per_device_train_batch_size,
        "max_length": max_length,
    }
    logger.info(f"Hyperparameters: {hyperparameters}")

    # -- Données ---------------------------------------------------------------
    # Dans le CSV de la session 2, la colonne `messages` est du texte où il
    # manque la virgule entre les deux messages : on la remet, puis on
    # retransforme le texte en vraie liste Python.
    def parse_messages(example):
        fixed_text = re.sub(r"\}\s*\{", "}, {", example["messages"])
        return {"messages": ast.literal_eval(fixed_text)}

    logger.info(f"Reading train dataset from {train_dataset.path}")
    dataset = HFDataset.from_csv(train_dataset.path).map(parse_messages)

    # Une partie du train sert de validation pendant l'entraînement
    split_dataset = dataset.train_test_split(test_size=validation_split_ratio, seed=42)
    logger.info(
        f"Train: {len(split_dataset['train'])} rows, "
        f"validation: {len(split_dataset['test'])} rows"
    )

    # -- Modèle ----------------------------------------------------------------
    # Phi-3 chargé en 4 bits pour prendre ~4 fois moins de mémoire GPU.
    # Calculs en float32 : le GPU T4 ne gère pas le bfloat16.
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float32,
    )
    logger.info(f"Loading {base_model_id}...")
    llm = AutoModelForCausalLM.from_pretrained(
        base_model_id, device_map="cuda:0", quantization_config=bnb_config
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    tokenizer.pad_token = tokenizer.unk_token
    tokenizer.pad_token_id = tokenizer.unk_token_id

    # LoRA : on gèle Phi-3 et on n'entraîne que de petites matrices ajoutées
    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["o_proj", "qkv_proj", "gate_up_proj", "down_proj"],
    )
    llm = prepare_model_for_kbit_training(llm)
    llm = get_peft_model(llm, lora_config)
    trainable_params, total_params = llm.get_nb_trainable_parameters()
    logger.info(
        f"Trainable parameters: {trainable_params:,} / {total_params:,} "
        f"({100 * trainable_params / total_params:.2f}%)"
    )

    # -- Entraînement ----------------------------------------------------------
    sft_config = SFTConfig(
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        gradient_accumulation_steps=1,
        per_device_train_batch_size=per_device_train_batch_size,
        auto_find_batch_size=True,
        max_length=max_length,
        packing=True,
        num_train_epochs=num_train_epochs,
        learning_rate=learning_rate,
        optim="paged_adamw_8bit",
        # Loss de validation calculée à la fin de chaque epoch
        eval_strategy="epoch",
        logging_steps=10,
        # Logs TensorBoard écrits dans l'artefact de métriques (donc dans le bucket)
        report_to=["tensorboard"],
        logging_dir=metrics.path,
        output_dir="./checkpoints",
        save_strategy="no",
    )
    trainer = SFTTrainer(
        model=llm,
        processing_class=tokenizer,
        args=sft_config,
        train_dataset=split_dataset["train"],
        eval_dataset=split_dataset["test"],
    )
    logger.info("Training...")
    train_result = trainer.train()
    eval_result = trainer.evaluate()

    # -- Sorties ---------------------------------------------------------------
    # Seuls les adaptateurs LoRA (+ le tokenizer) sont sauvegardés, pas tout Phi-3
    logger.info(f"Saving LoRA adapter to {model.path}")
    trainer.save_model(model.path)
    model.metadata["base_model_id"] = base_model_id

    # Métriques visibles dans la console Vertex AI
    for name, value in hyperparameters.items():
        metrics.log_metric(name, value)
    metrics.log_metric("trainable_params", trainable_params)
    metrics.log_metric("train_loss", train_result.training_loss)
    metrics.log_metric("eval_loss", eval_result["eval_loss"])

    logger.info("Fine-tuning process completed successfully")
