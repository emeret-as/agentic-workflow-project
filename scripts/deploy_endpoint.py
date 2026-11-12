"""Deploy a registered model to a new Vertex AI Endpoint.

Usage :
    uv run --env-file .env python -m scripts.deploy_endpoint \
        --model emeret-ureboullet_model --endpoint-name emeret-ureboullet

Le déploiement prend 15 à 30 minutes. L'endpoint facture tant qu'il existe
(pas de scale-to-zero) : le supprimer avec `--delete <ENDPOINT_ID>` après usage.
"""

import argparse

from google.cloud import aiplatform

from src.constants import PROJECT_ID, REGION


def deploy(
    model_name: str, endpoint_name: str, machine_type: str = "n1-standard-8"
) -> aiplatform.Endpoint:
    """Deploy the latest version of a registered model to a new endpoint."""
    models = aiplatform.Model.list(filter=f'display_name="{model_name}"')
    if not models:
        raise SystemExit(f"Aucun modèle nommé {model_name!r} dans le registre")
    endpoint = aiplatform.Endpoint.create(display_name=endpoint_name)
    print(f"ENDPOINT_ID={endpoint.name}", flush=True)
    endpoint.deploy(
        model=models[0],
        deployed_model_display_name=model_name,
        # n1-standard-4 si le quota CustomModelServingCPUsPerProjectPerRegion
        # est saturé par les endpoints des autres équipes
        machine_type=machine_type,
        accelerator_type="NVIDIA_TESLA_T4",
        accelerator_count=1,
        # Un seul nœud : Vertex AI ne sait pas descendre à zéro
        min_replica_count=1,
        max_replica_count=1,
    )
    return endpoint


def delete(endpoint_id: str) -> None:
    """Undeploy the model and delete the endpoint to stop billing."""
    aiplatform.Endpoint(endpoint_id).delete(force=True)
    print(f"Endpoint {endpoint_id} supprimé")


def main() -> None:
    """Deploy a model or delete an endpoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="Nom affiché du modèle dans le registre")
    parser.add_argument("--endpoint-name", default="emeret-crm-endpoint")
    parser.add_argument("--machine-type", default="n1-standard-8")
    parser.add_argument("--delete", metavar="ENDPOINT_ID", help="Supprimer l'endpoint")
    args = parser.parse_args()

    aiplatform.init(project=PROJECT_ID, location=REGION)
    if args.delete:
        delete(args.delete)
    elif args.model:
        endpoint = deploy(args.model, args.endpoint_name, args.machine_type)
        print(f"Endpoint prêt : {endpoint.resource_name}")
    else:
        parser.error("--model ou --delete est requis")


if __name__ == "__main__":
    main()
