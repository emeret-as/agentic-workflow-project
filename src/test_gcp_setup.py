# Script de test de la configuration GCP
import os

from dotenv import load_dotenv
from google.cloud import aiplatform, storage

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
region = os.getenv("GCP_REGION")
bucket_name = os.getenv("GCP_BUCKET_NAME")

print(f"Project ID : {project_id}")
print(f"Region     : {region}")
print(f"Bucket     : {bucket_name}")

# Test Vertex AI
print("\n--- Test Vertex AI ---")
aiplatform.init(project=project_id, location=region)
print("✅ Vertex AI client initialisé avec succès")

# Test GCS
print("\n--- Test Google Cloud Storage ---")
storage_client = storage.Client(project=project_id)
bucket = storage_client.get_bucket(bucket_name)
blobs = list(bucket.list_blobs())
print(f"✅ Bucket '{bucket_name}' accessible — {len(blobs)} fichier(s) trouvé(s) :")
for blob in blobs:
    print(f"   - {blob.name}")
