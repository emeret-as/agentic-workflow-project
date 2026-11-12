"""Inference component for Vertex AI pipeline."""

from kfp.dsl import Dataset, Input, Model, Output, component


@component(
    # Même image GPU que le fine-tuning
    base_image="pytorch/pytorch:2.8.0-cuda12.9-cudnn9-devel",
    packages_to_install=[
        "transformers==4.46.3",
        "peft==0.13.2",
        "accelerate==1.15.0",
        "huggingface-hub==0.36.2",
        "bitsandbytes==0.48.2",
        "google-cloud-storage==3.16.0",
        "pandas==2.3.3",
    ],
)
def inference_component(
    model: Input[Model],
    test_dataset: Input[Dataset],
    predictions: Output[Dataset],
    max_new_tokens: int = 160,
    use_base_model: bool = False,
) -> None:
    """Extract CRM records from the test notes with the fine-tuned model.

    `use_base_model=True` : même inférence avec Phi-3 seul (sans les adaptateurs
    LoRA), pour mesurer ce qu'apporte le fine-tuning (pipeline d'évaluation du
    modèle de base).
    """
    import ast
    import json
    import logging
    import re
    from pathlib import Path
    from typing import Any

    import pandas as pd
    import torch
    from google.cloud import storage
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting inference process...")

    # -- Les 4 fonctions de local_tests/inference_test.py ----------------------
    def download_model(model_uri: str, local_dir: str):
        """Download model from GCS to local directory."""
        bucket_name, prefix = model_uri.removeprefix("gs://").split("/", 1)
        prefix = prefix.rstrip("/") + "/"
        client = storage.Client()
        for blob in client.list_blobs(bucket_name, prefix=prefix):
            if blob.name.endswith("/"):
                continue
            local_path = Path(local_dir) / blob.name.removeprefix(prefix)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(local_path)

    def build_prompt(tokenizer: AutoTokenizer, user_content: str):
        """Build a prompt from the user message applying the chat template."""
        messages = [{"role": "user", "content": user_content}]
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    def generate_response(
        model: AutoModelForCausalLM,
        tokenizer: AutoTokenizer,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        """Generate a response from the model given a prompt."""
        inputs = tokenizer(prompt, add_special_tokens=False, return_tensors="pt").to(
            model.device
        )
        model.eval()
        output_tokens = model.generate(**inputs, **kwargs)
        return tokenizer.batch_decode(output_tokens, skip_special_tokens=False)[0]

    def extract_response(model_output: str) -> str:
        """Extract the actual response from the model output."""
        match = re.search(
            r"<\|assistant\|>(.*?)(?:<\|end\|>|<\|endoftext\|>|$)",
            model_output,
            re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    # -- Modèle ----------------------------------------------------------------
    local_model_dir = "./fine-tuned-model"
    logger.info(f"Downloading model from {model.uri}")
    download_model(model.uri, local_model_dir)

    # Le dossier ne contient que les adaptateurs LoRA : from_pretrained lit
    # adapter_config.json, recharge Phi-3 depuis Hugging Face, puis pose les
    # adaptateurs dessus. Phi-3 est chargé en 4 bits, comme à l'entraînement.
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float32,
    )
    model_source = local_model_dir
    if use_base_model:
        # Modèle de base : on lit son identifiant Hugging Face dans la config LoRA
        adapter_config = json.loads(
            (Path(local_model_dir) / "adapter_config.json").read_text()
        )
        model_source = adapter_config["base_model_name_or_path"]
        logger.info(f"Base model only (no LoRA adapters): {model_source}")
    llm = AutoModelForCausalLM.from_pretrained(
        model_source, device_map="cuda:0", quantization_config=bnb_config
    )
    tokenizer = AutoTokenizer.from_pretrained(local_model_dir)

    # -- Données de test -------------------------------------------------------
    # Même correction qu'au fine-tuning : virgule manquante entre les 2 messages
    logger.info(f"Reading test dataset from {test_dataset.path}")
    test_df = pd.read_csv(test_dataset.path)
    conversations = test_df["messages"].apply(
        lambda text: ast.literal_eval(re.sub(r"\}\s*\{", "}, {", text))
    )

    # -- Prédictions -----------------------------------------------------------
    rows = []
    for i, conversation in enumerate(conversations):
        # message user = consigne + note ; message assistant = vraie fiche JSON
        user_content = conversation[0]["content"]
        reference = conversation[1]["content"]
        prompt = build_prompt(tokenizer, user_content)
        model_output = generate_response(
            llm, tokenizer, prompt, max_new_tokens=max_new_tokens, do_sample=False
        )
        rows.append(
            {
                "user_input": user_content,
                "reference": reference,
                "extracted_response": extract_response(model_output),
            }
        )
        logger.info(f"[{i + 1}/{len(conversations)}] {rows[-1]}")

    # Format conseillé par l'énoncé pour ragas
    logger.info(f"Writing predictions to {predictions.path}")
    pd.DataFrame(rows).to_csv(predictions.path, index=False)

    logger.info("Inference process completed successfully")
