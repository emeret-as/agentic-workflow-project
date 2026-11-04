# =============================================================================
# Test local de l'inférence (session 3, partie 2)
# =============================================================================
# On écrit les fonctions une par une avant de les mettre dans un composant
# Kubeflow.
# À lancer depuis la racine du projet :
#   uv run --env-file .env python -W ignore local_tests/inference_test.py
# =============================================================================

import re
from pathlib import Path
from typing import Any

from google.cloud import storage
from transformers import AutoModelForCausalLM, AutoTokenizer

# Artefact `model` de l'étape fine-tuning du pipeline du 03/11
# (console Vertex AI -> pipeline -> fine-tuning-component -> model)
MODEL_URI = (
    "gs://emeret-llmops/vertexai-pipeline-root/123905721265/"
    "model-training-pipeline-20261103172710/"
    "fine-tuning-component_7221776127113560064/model"
)
LOCAL_MODEL_DIR = "models/phi3-yoda-adapter"


# -----------------------------------------------------------------------------
# 1. download_model : bucket -> dossier local
# -----------------------------------------------------------------------------
def download_model(model_uri: str, local_dir: str):
    """Download model from GCS to local directory."""
    # "gs://bucket/chemin/model" -> bucket = "bucket", prefix = "chemin/model/"
    bucket_name, prefix = model_uri.removeprefix("gs://").split("/", 1)
    prefix = prefix.rstrip("/") + "/"

    client = storage.Client()
    # list_blobs renvoie tous les fichiers dont le nom commence par prefix
    for blob in client.list_blobs(bucket_name, prefix=prefix):
        if blob.name.endswith("/"):  # « dossier » vide créé par GCS, rien à télécharger
            continue
        local_path = Path(local_dir) / blob.name.removeprefix(prefix)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path)


# -----------------------------------------------------------------------------
# 2. build_prompt : phrase -> conversation au format de Phi-3
# -----------------------------------------------------------------------------
def build_prompt(tokenizer: AutoTokenizer, sentence: str):
    """Build a prompt from a sentence applying the chat template.

    Output string should look like:
        <|user|>
        The Force is strong in you!<|end|>
        <|assistant|>
    """
    # Même format qu'à l'entraînement : un seul message, celui de l'utilisateur
    messages = [{"role": "user", "content": sentence}]
    # add_generation_prompt=True ajoute « <|assistant|> » à la fin :
    # c'est le signal pour que le modèle écrive la réponse
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )


# -----------------------------------------------------------------------------
# 3. generate_response : prompt -> texte généré par le modèle
# -----------------------------------------------------------------------------
def generate_response(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    prompt: str,
    **kwargs: Any,
) -> str:
    """Generate a response from the model given a prompt."""
    # Texte -> numéros de tokens (le prompt contient déjà les balises spéciales,
    # donc on n'en rajoute pas), envoyés sur la même machine que le modèle
    inputs = tokenizer(prompt, add_special_tokens=False, return_tensors="pt").to(
        model.device
    )
    model.eval()  # mode prédiction : désactive le dropout de l'entraînement
    # kwargs = paramètres de génération, ex. max_new_tokens=64
    output_tokens = model.generate(**inputs, **kwargs)
    # Numéros de tokens -> texte. On garde les balises (<|end|>…) :
    # extract_response s'en sert pour isoler la réponse
    return tokenizer.batch_decode(output_tokens, skip_special_tokens=False)[0]


# -----------------------------------------------------------------------------
# 4. extract_response : sortie complète -> seulement la réponse du modèle
# -----------------------------------------------------------------------------
def extract_response(model_output: str) -> str:
    """Extract the actual response from the model output.

    If input string looks like this:
        <|user|>
        The Force is strong in you!<|end|>
        <|assistant|>
        Strong in you, the Force is. Yes, hrrmmm.<|end|>

    The output should be:
        Strong in you, the Force is. Yes, hrrmmm.
    """
    # On prend ce qui est entre <|assistant|> et la balise de fin (<|end|>,
    # <|endoftext|>, ou la fin du texte si le modèle a été coupé avant).
    # re.DOTALL : le « . » accepte aussi les retours à la ligne
    match = re.search(
        r"<\|assistant\|>(.*?)(?:<\|end\|>|<\|endoftext\|>|$)", model_output, re.DOTALL
    )
    return match.group(1).strip() if match else ""


if __name__ == "__main__":
    download_model(MODEL_URI, LOCAL_MODEL_DIR)
    print("Fichiers téléchargés :")
    for path in sorted(Path(LOCAL_MODEL_DIR).iterdir()):
        print(f"  {path.name} ({path.stat().st_size / 1e6:.2f} Mo)")

    # Le tokenizer a été sauvegardé avec les adaptateurs LoRA (quelques Mo)
    tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR)
    print("\nPrompt construit :")
    print(build_prompt(tokenizer, "The Force is strong in you!"))
