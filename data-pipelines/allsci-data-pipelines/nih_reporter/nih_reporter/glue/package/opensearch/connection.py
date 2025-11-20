from opensearchpy import OpenSearch, helpers
import json
from datetime import datetime

def initialize_opensearch(opensearch_config: dict):
    """
    Initializes and returns an OpenSearch client instance.

    The function connects to an OpenSearch cluster using the configuration provided
    in the `opensearch_config` dictionary. This includes connection details such as 
    the host, port, and authentication credentials.

    Returns:
        OpenSearch: An instance of the OpenSearch client configured to communicate 
        with the specified cluster.

    Configuration Details:
        - `host`: The hostname or IP address of the OpenSearch cluster.
        - `port`: The port on which the OpenSearch cluster is running.
        - `user`: The username for authentication.
        - `password`: The password for authentication.
        - `use_ssl`: Ensures SSL is used for secure communication.
        - `verify_certs`: Verifies the SSL certificates for secure communication.
    """
    client = OpenSearch(
        hosts=[{
            "host": opensearch_config["host"],
            "port": opensearch_config["port"]
        }],
        http_auth=(
            opensearch_config["opensearch.net.http.auth.user"],
            opensearch_config["opensearch.net.http.auth.pass"]
        ),
        use_ssl=True,
        verify_certs=True,
    )
    return client


def configure_index(client, index_name, restore=False):
    """Configure OpenSearch index for bulk ingestion."""
    
    if not restore:
        print(f"Configuring index {index_name} for bulk ingestion...")
        client.indices.put_settings(
            index=index_name,
            body={"index": {"refresh_interval": -1, "mapping.total_fields.limit": 5000}}
        )
        print(f"Index {index_name} configured.")
        
    else:
        print(f"Restoring settings for index {index_name}...")
        client.indices.put_settings(
            index=index_name,
            body={"index": {"refresh_interval": "1s", "mapping.total_fields.limit": 1000}}
        )
        print(f"Settings restored for index {index_name}.")
