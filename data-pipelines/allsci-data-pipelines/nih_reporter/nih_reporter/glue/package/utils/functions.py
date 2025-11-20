import datetime
import json
import re

import boto3
import pandas as pd


s3 = boto3.client("s3")


def get_secret(secret_name, region_name="us-east-1"):
    """
    Retrieve a secret from AWS Secrets Manager.

    Parameters:
        secret_name (str): The name or ARN of the secret.
        region_name (str): AWS region where the secret is stored. Default is 'us-east-1'.

    Returns:
        dict: The secret value as a dictionary.
    """
    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    try:
        # Retrieve the secret
        response = client.get_secret_value(SecretId=secret_name)

        return json.loads(response["SecretString"])

    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {e}")
        return None


def extract_date_from_s3_key(s3_key: str) -> str:
    """
    Extracts dates from the S3 key using regex.

    Parameters:
    s3_key (str): The S3 key from which to extract dates.

    Returns:
    list: A list of date strings in 'YYYY-MM-DD' format.
    """
    match = re.search(r'year=(\d{4})/month=(\d{2})/day=(\d{2})', s3_key)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    else:
        print("Date not found in the path.")


def get_latest_control_file(bucket: str, base_prefix: str, year: str, month: str) -> str:

    # Format prefix: control_files/drugs/year=2025/month=04/
    prefix = f"{base_prefix}/year={year}/month={month}/"

    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        raise FileNotFoundError(f"No files found in s3://{bucket}/{prefix}")

    # Filter only control_*.json files
    control_files = [
        obj["Key"] for obj in response["Contents"]
        if obj["Key"].endswith(".json") and "control_" in obj["Key"]
    ]

    if not control_files:
        raise FileNotFoundError(f"No control_*.json files found in s3://{bucket}/{prefix}")

    # Sort files by name (latest date will be last due to naming)
    control_files_sorted = sorted(control_files, reverse=True)

    latest_key = control_files_sorted[0]
    print(f"latest key {latest_key}")

    response = s3.get_object(Bucket=bucket, Key=latest_key)
    content = response["Body"].read().decode("utf-8")
    dict_content = json.loads(content)

    return dict_content["max_part_id"], latest_key


def put_control_file(bucket: str, base_prefix: str, max_part_id: int):

    # Get today's date
    today = datetime.datetime.now()
    year = today.strftime("%Y")
    month = today.strftime("%m")
    day = today.strftime("%d")

    # File content
    content = {
        "max_part_id": max_part_id
    }

    # File key
    key = f"{base_prefix}/year={year}/month={month}/control_{year}-{month}-{day}.json"

    # Upload to S3
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(content, indent=4),
        ContentType="application/json"
    )

    print(f"Control file successfully uploaded at s3://{bucket}/{key}")


def read_json_from_s3(bucket_name: str, file_key: str) -> dict:
    """
    Read a small JSON file from S3 and return its contents

    Args:
        bucket_name (str): S3 bucket name
        file_key (str): S3 object key (file path)

    Returns:
        dict: JSON content as a dictionary
    """
    s3 = boto3.client('s3')

    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        json_content = response['Body'].read().decode('utf-8')
        return json.loads(json_content)

    except Exception as e:
        print(f"Error reading JSON file from S3: {e}")
        return None


def write_json_to_s3(data: dict, bucket_name: str, file_key: str) -> bool:
    """
    Write a JSON file to S3

    Args:
        data (dict or DataFrame): Data to write as JSON
        bucket_name (str): S3 bucket name
        file_key (str): S3 object key (file path)

    Returns:
        bool: True if successful, False otherwise
    """
    s3 = boto3.client('s3')

    try:
        if isinstance(data, pd.DataFrame):
            json_content = data.to_json()
        else:
            json_content = pd.Series(data).to_json()

        s3.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=json_content,
            ContentType='application/json'
        )

        print(f"Successfully wrote JSON file to s3://{bucket_name}/{file_key}")
        return True

    except Exception as e:
        print(f"Error writing JSON file to S3: {e}")
        return False


# def update_flag(bucket_name: str, processor_flag: dict, data_sources: list[str], layers=None) -> None:
#     """
#     Update the flag file with the latest processing date.

#     Returns:
#         bool: True if the update was successful, False otherwise.
#     """
#     current_date = pd.Timestamp.now(tz=datetime.timezone.utc).isoformat()
#     processor_flag['last_updated_at'] = current_date

#     if layers is None:
#         source_layer = processor_flag['source_layer']
#         target_layer = processor_flag['target_layer']

#     for _source in data_sources:
#         processor_flag['sources_last_updated_at'][f'{source_layer}_{_source}'] = current_date

#     return write_json_to_s3(
#         processor_flag,
#         bucket_name,
#         f"control_flags/{target_layer}/{processor_flag['job_name']}/flag.json"
#     )

def update_flag(bucket_name: str, processor_flag: dict, data_sources: list[str], layers=None) -> None:
    """
    Update the flag file with the latest processing date.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    current_date = pd.Timestamp.now(tz=datetime.timezone.utc).isoformat()
    processor_flag['last_updated_at'] = current_date

    if layers is None:
        source_layer = processor_flag['source_layer']
        target_layer = processor_flag['target_layer']

    for _source in data_sources:
        source_flag = read_json_from_s3(
            bucket_name,
            f"control_flags/{source_layer}/{_source}/flag.json"
        )
        source_last_updated_at = source_flag['last_updated_at']
        processor_flag['sources_last_updated_at'][f'{source_layer}_{_source}'] = source_last_updated_at

    return write_json_to_s3(
        processor_flag,
        bucket_name,
        f"control_flags/{target_layer}/{processor_flag['job_name']}/flag.json"
    )
