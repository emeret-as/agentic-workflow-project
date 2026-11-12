"""Custom handler for the pre-built Hugging Face inference container on Vertex AI.

Ce fichier est uploadé tel quel (sous le nom `handler.py`) à la racine du dossier
des artefacts du modèle : il doit donc être autonome (aucun import depuis `src`).
Le conteneur le charge et appelle `EndpointHandler.__call__` pour chaque requête.

Format de requête (imposé par Vertex AI) :
    {"instances": [{"input": "<|user|>\\n...<|end|>\\n<|assistant|>"}],
     "parameters": {"max_new_tokens": 160, ...}}
Format de réponse :
    {"predictions": ["<|user|>...<|assistant|>... <|end|>"]}
"""

import os
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Dossier où le conteneur copie les artefacts du modèle depuis GCS
MODEL_DIR = "/opt/huggingface/model"
# "cuda:0" sur l'endpoint (T4). En local, passer "cpu" ou "mps" via la variable
DEVICE_MAP = os.getenv("HANDLER_DEVICE_MAP", "cuda:0")

# Paramètres de génération par défaut, écrasés par ceux de la requête
DEFAULT_GENERATION_PARAMETERS: dict[str, Any] = {
    "max_new_tokens": 160,
    "do_sample": False,
}


class EndpointHandler:
    """Handler for processing inference requests using a Hugging Face model."""

    def __init__(self, model_dir: str = MODEL_DIR) -> None:
        """Load tokenizer and model from the specified directory."""
        # Le dossier ne contient que les adaptateurs LoRA et le tokenizer :
        # from_pretrained lit adapter_config.json, recharge Phi-3 depuis Hugging
        # Face puis pose les adaptateurs dessus (intégration PEFT de transformers).
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        # float16 : Phi-3 (~7,6 Go) tient sur un T4 (16 Go) sans bitsandbytes
        self.model = AutoModelForCausalLM.from_pretrained(
            model_dir, torch_dtype=torch.float16, device_map=DEVICE_MAP
        ).eval()  # mode prédiction : désactive le dropout

    def __call__(self, data: dict[str, Any]) -> dict[str, list[Any]]:
        """Run inference on a Vertex AI prediction request."""
        instances = data.get("instances", [])
        parameters = {**DEFAULT_GENERATION_PARAMETERS, **data.get("parameters", {})}

        predictions: list[str] = []
        for instance in instances:
            # Le prompt arrive déjà avec le chat template appliqué
            inputs = self.tokenizer(
                instance["input"], add_special_tokens=False, return_tensors="pt"
            ).to(self.model.device)
            with torch.no_grad():
                output_tokens = self.model.generate(
                    **inputs,
                    eos_token_id=self.tokenizer.eos_token_id,
                    **parameters,
                )
            # On garde les balises spéciales : le client extrait la réponse
            predictions.append(
                self.tokenizer.batch_decode(output_tokens, skip_special_tokens=False)[0]
            )

        return {"predictions": predictions}
