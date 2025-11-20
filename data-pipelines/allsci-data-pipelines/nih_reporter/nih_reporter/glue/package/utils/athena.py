import time

import boto3
import pandas as pd


athena_client = boto3.client("athena", region_name="us-east-1")


def execute_athena_query(query: str, database: str, output_location: str) -> str:
    """
    Executes an AWS Athena query and returns the QueryExecutionId.

    Parameters:
        query (str): The SQL query to execute.
        database (str): The Athena database to query.
        output_location (str): The S3 path where query results are stored.

    Returns:
        str: The QueryExecutionId of the executed query.
    """
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )
    return response["QueryExecutionId"]


def wait_for_query_completion(query_execution_id: str, sleep_time: int = 10) -> None:
    """
    Waits for an Athena query to complete.

    Parameters:
        query_execution_id (str): The execution ID of the Athena query.
        sleep_time (int): Time (in seconds) between status checks.

    Raises:
        Exception: If the query fails or gets cancelled.
    """
    while True:
        response = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        status = response["QueryExecution"]["Status"]["State"]

        if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            if status != "SUCCEEDED":
                raise Exception(f"Athena query failed or was cancelled: {status}")
            break

        time.sleep(sleep_time)


def get_athena_query_results(query_execution_id: str) -> pd.DataFrame:
    """
    Fetches the results of an Athena query and returns them as a Pandas DataFrame.

    Parameters:
        query_execution_id (str): The execution ID of the Athena query.

    Returns:
        pd.DataFrame: The query results as a Pandas DataFrame.
    """
    results_paginator = athena_client.get_paginator("get_query_results")
    response_iterator = results_paginator.paginate(QueryExecutionId=query_execution_id)

    rows = []
    columns = []

    for page in response_iterator:
        for idx, row in enumerate(page["ResultSet"]["Rows"]):
            data = [col.get("VarCharValue", None) for col in row["Data"]]

            if idx == 0:
                columns = data  # First row contains column names
            else:
                rows.append(data)

    return pd.DataFrame(rows, columns=columns)


def query_athena(query: str, database: str, output_location: str, return_results: bool = True) -> pd.DataFrame:
    """
    Executes an Athena query and returns the results as a Pandas DataFrame.

    Parameters:
        query (str): The SQL query to execute.
        database (str): The Athena database to query.
        output_location (str): The S3 path where query results are stored.

    Returns:
        pd.DataFrame: The query results as a Pandas DataFrame.
    """
    query_execution_id = execute_athena_query(query, database, output_location)
    wait_for_query_completion(query_execution_id)
    print(f"Query executed successfully. Query execution id: {query_execution_id}")

    if return_results:
        return get_athena_query_results(query_execution_id)
