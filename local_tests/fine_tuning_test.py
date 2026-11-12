# =============================================================================
# Test local du fine-tuning (session 3, partie 1)
# =============================================================================
# Remplace le notebook de l'énoncé : on teste le code morceau par morceau
# avant de le mettre dans un composant Kubeflow.
# À lancer depuis la racine du projet :
#   uv run python -W ignore local_tests/fine_tuning_test.py
# =============================================================================

from peft import LoraConfig
from trl import SFTConfig

# -----------------------------------------------------------------------------
# Hyper-paramètres clés
# -----------------------------------------------------------------------------
# Regroupés dans un dictionnaire pour pouvoir les enregistrer avec les
# métriques, et plus tard les passer en paramètres du composant.
HYPERPARAMETERS = {
    # LoRA
    "lora_r": 8,  # taille des petites matrices ajoutées : plus grand = plus de paramètres entraînés
    "lora_alpha": 16,  # force de l'effet de LoRA sur le modèle
    "lora_dropout": 0.05,  # 5 % de valeurs éteintes au hasard pendant l'entraînement (évite d'apprendre par cœur)
    # Entraînement
    "num_train_epochs": 3,  # nombre de passages sur tout le jeu d'entraînement
    "learning_rate": 3e-4,  # taille des corrections à chaque mise à jour du modèle
    "per_device_train_batch_size": 16,  # nombre d'exemples traités en même temps
    "max_length": 64,  # longueur maximale d'un exemple, en tokens (morceaux de mots)
}

# -----------------------------------------------------------------------------
# LoraConfig : où et comment ajouter LoRA
# -----------------------------------------------------------------------------
# LoRA ne modifie pas les poids de Phi-3 : il ajoute de petites matrices à
# certaines couches, et on n'entraîne que celles-là.
lora_config = LoraConfig(
    r=HYPERPARAMETERS["lora_r"],
    lora_alpha=HYPERPARAMETERS["lora_alpha"],
    lora_dropout=HYPERPARAMETERS["lora_dropout"],
    bias="none",
    task_type="CAUSAL_LM",  # modèle qui génère du texte mot après mot
    # Couches de Phi-3 qui reçoivent LoRA : l'attention (qkv_proj, o_proj)
    # et le réseau qui suit (gate_up_proj, down_proj)
    target_modules=["o_proj", "qkv_proj", "gate_up_proj", "down_proj"],
)

# -----------------------------------------------------------------------------
# BitsAndBytesConfig : non testé ici
# -----------------------------------------------------------------------------
# Il charge le modèle en 4 bits pour qu'il prenne moins de mémoire, mais la
# librairie bitsandbytes ne s'installe pas sur Mac. Il ira directement dans
# le composant qui tourne dans le cloud.

# -----------------------------------------------------------------------------
# SFTConfig : les réglages de l'entraînement
# -----------------------------------------------------------------------------
sft_config = SFTConfig(
    # Économiser la mémoire de la carte graphique
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    gradient_accumulation_steps=1,
    per_device_train_batch_size=HYPERPARAMETERS["per_device_train_batch_size"],
    auto_find_batch_size=True,  # divise la taille de lot par 2 si la mémoire déborde
    # Données
    max_length=HYPERPARAMETERS["max_length"],
    packing=True,  # colle plusieurs exemples courts ensemble pour éviter le remplissage
    # Entraînement
    num_train_epochs=HYPERPARAMETERS["num_train_epochs"],
    learning_rate=HYPERPARAMETERS["learning_rate"],
    optim="paged_adamw_8bit",
    # Suivi : les métriques sont écrites pour TensorBoard dans logging_dir
    logging_steps=10,
    report_to=["tensorboard"],
    logging_dir="./logs",
    output_dir="./phi3-mini-yoda-adapter",
)

print("Hyper-paramètres :", HYPERPARAMETERS)
print("\nLoraConfig :", lora_config)
print(
    "\nSFTConfig : max_length =", sft_config.max_length,
    "| epochs =", sft_config.num_train_epochs,
    "| report_to =", sft_config.report_to,
    "| logging_dir =", sft_config.logging_dir,
)
