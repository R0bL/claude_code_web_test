"""
NIH RePORTER API Ingestion Lambda Function

This Lambda function queries the NIH RePORTER API v2 for project data,
handles pagination, respects rate limits, and saves complete raw JSON
responses to S3 landing zone.

Author: AllSci Data Pipeline
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from io import StringIO

import boto3
import requests
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
LANDING_ZONE_BUCKET = os.environ.get('LANDING_ZONE_BUCKET')
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.reporter.nih.gov')
RATE_LIMIT_DELAY = float(os.environ.get('RATE_LIMIT_DELAY', '1.0'))  # seconds
MAX_RECORDS_PER_REQUEST = int(os.environ.get('MAX_RECORDS_PER_REQUEST', '500'))
MAX_OFFSET = int(os.environ.get('MAX_OFFSET', '14999'))

# Initialize AWS clients
s3_client = boto3.client('s3')


class NIHReporterAPIError(Exception):
    """Custom exception for NIH RePORTER API errors."""
    pass


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for NIH RePORTER API ingestion.

    Args:
        event: Lambda event containing:
            - fiscal_years: List of fiscal years to query (default: current year)
            - include_fields: Optional list of specific fields to include
            - additional_criteria: Optional dict of additional search criteria

        context: Lambda context object

    Returns:
        Dict containing:
            - status: Success/failure status
            - files_processed: List of S3 file paths created
            - total_records: Total number of records ingested
            - errors: List of any errors encountered
    """
    try:
        logger.info(f"Starting NIH RePORTER ingestion with event: {json.dumps(event)}")

        # Parse input parameters
        fiscal_years = event.get('fiscal_years', [datetime.now().year])
        include_fields = event.get('include_fields', None)  # None = get all fields
        additional_criteria = event.get('additional_criteria', {})

        # Validate inputs
        if not isinstance(fiscal_years, list):
            fiscal_years = [fiscal_years]

        if not LANDING_ZONE_BUCKET:
            raise ValueError("LANDING_ZONE_BUCKET environment variable not set")

        # Process each fiscal year
        all_files_processed = []
        total_records = 0
        errors = []

        for fiscal_year in fiscal_years:
            try:
                logger.info(f"Processing fiscal year: {fiscal_year}")
                files, record_count = process_fiscal_year(
                    fiscal_year=fiscal_year,
                    include_fields=include_fields,
                    additional_criteria=additional_criteria
                )
                all_files_processed.extend(files)
                total_records += record_count
                logger.info(f"Completed fiscal year {fiscal_year}: {record_count} records, {len(files)} files")

            except Exception as e:
                error_msg = f"Error processing fiscal year {fiscal_year}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Prepare response
        response = {
            'status': 'success' if not errors else 'partial_success' if all_files_processed else 'failed',
            'files_processed': all_files_processed,
            'total_records': total_records,
            'fiscal_years_processed': fiscal_years,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Ingestion complete: {json.dumps(response)}")
        return response

    except Exception as e:
        logger.error(f"Critical error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }


def process_fiscal_year(
    fiscal_year: int,
    include_fields: Optional[List[str]] = None,
    additional_criteria: Optional[Dict[str, Any]] = None
) -> tuple[List[str], int]:
    """
    Process a single fiscal year, handling pagination and saving to S3.

    Args:
        fiscal_year: Fiscal year to query
        include_fields: Optional list of fields to include (None = all fields)
        additional_criteria: Optional additional search criteria

    Returns:
        Tuple of (list of S3 file paths, total record count)
    """
    files_created = []
    total_records_processed = 0
    offset = 0
    batch_num = 0

    while offset <= MAX_OFFSET:
        # Build request payload
        payload = build_request_payload(
            fiscal_year=fiscal_year,
            offset=offset,
            limit=MAX_RECORDS_PER_REQUEST,
            include_fields=include_fields,
            additional_criteria=additional_criteria
        )

        # Query API
        logger.info(f"Querying API for FY{fiscal_year}, offset={offset}, limit={MAX_RECORDS_PER_REQUEST}")
        response_data = query_api(payload)

        # Extract results
        results = response_data.get('results', [])
        total_available = response_data.get('meta', {}).get('total', 0)

        logger.info(f"Received {len(results)} records (total available: {total_available})")

        if not results:
            logger.info(f"No more results for FY{fiscal_year} at offset {offset}")
            break

        # Save batch to S3
        s3_path = save_batch_to_s3(
            results=results,
            fiscal_year=fiscal_year,
            batch_num=batch_num
        )

        files_created.append(s3_path)
        total_records_processed += len(results)

        # Check if we've retrieved all records
        if offset + len(results) >= total_available:
            logger.info(f"Retrieved all {total_available} records for FY{fiscal_year}")
            break

        # Check if we've hit the max offset limit
        if offset + MAX_RECORDS_PER_REQUEST > MAX_OFFSET:
            logger.warning(
                f"Reached max offset limit ({MAX_OFFSET}). "
                f"Retrieved {total_records_processed} of {total_available} total records. "
                f"Consider refining search criteria to retrieve remaining records."
            )
            break

        # Update offset for next batch
        offset += MAX_RECORDS_PER_REQUEST
        batch_num += 1

        # Rate limiting - wait before next request
        time.sleep(RATE_LIMIT_DELAY)

    return files_created, total_records_processed


def build_request_payload(
    fiscal_year: int,
    offset: int,
    limit: int,
    include_fields: Optional[List[str]] = None,
    additional_criteria: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build the request payload for the NIH RePORTER API.

    Args:
        fiscal_year: Fiscal year to query
        offset: Pagination offset
        limit: Number of records per page
        include_fields: Optional list of fields to include
        additional_criteria: Optional additional search criteria

    Returns:
        Request payload dictionary
    """
    # Base criteria
    criteria = {
        'fiscal_years': [fiscal_year]
    }

    # Merge additional criteria
    if additional_criteria:
        criteria.update(additional_criteria)

    # Build payload
    payload = {
        'criteria': criteria,
        'offset': offset,
        'limit': limit
    }

    # Add include_fields if specified
    # If not specified, API returns all fields by default
    if include_fields:
        payload['include_fields'] = include_fields

    return payload


def query_api(payload: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    """
    Query the NIH RePORTER API with retry logic.

    Args:
        payload: Request payload
        max_retries: Maximum number of retry attempts

    Returns:
        API response as dictionary

    Raises:
        NIHReporterAPIError: If API request fails after retries
    """
    url = f"{API_BASE_URL}/v2/projects/search"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )

            # Check for successful response
            if response.status_code == 200:
                return response.json()

            # Handle specific error codes
            elif response.status_code == 429:  # Rate limit
                wait_time = (attempt + 1) * RATE_LIMIT_DELAY * 2
                logger.warning(f"Rate limit hit, waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue

            elif response.status_code >= 500:  # Server error
                wait_time = (attempt + 1) * 2
                logger.warning(f"Server error {response.status_code}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            else:  # Other errors
                raise NIHReporterAPIError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )

        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout on attempt {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 2)
                continue
            raise NIHReporterAPIError("API request timed out after max retries")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Request exception on attempt {attempt + 1}/{max_retries}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 2)
                continue
            raise NIHReporterAPIError(f"API request failed: {str(e)}")

    raise NIHReporterAPIError(f"API request failed after {max_retries} attempts")


def save_batch_to_s3(
    results: List[Dict[str, Any]],
    fiscal_year: int,
    batch_num: int
) -> str:
    """
    Save a batch of results to S3 in JSONL format.

    Args:
        results: List of project records
        fiscal_year: Fiscal year
        batch_num: Batch number

    Returns:
        S3 path of saved file

    Raises:
        ClientError: If S3 upload fails
    """
    # Generate S3 key
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    s3_key = f"nih_reporter/projects/projects_FY{fiscal_year}_batch{batch_num:04d}_{timestamp}.jsonl"

    try:
        # Convert to JSONL format
        jsonl_buffer = StringIO()
        for record in results:
            # Add ingestion metadata to each record
            record['_ingestion_metadata'] = {
                'ingestion_timestamp': datetime.utcnow().isoformat(),
                'fiscal_year': fiscal_year,
                'batch_number': batch_num,
                'source': 'nih_reporter_api_v2'
            }
            jsonl_buffer.write(json.dumps(record) + '\n')

        # Upload to S3
        s3_client.put_object(
            Bucket=LANDING_ZONE_BUCKET,
            Key=s3_key,
            Body=jsonl_buffer.getvalue().encode('utf-8'),
            ContentType='application/x-ndjson',
            Metadata={
                'fiscal_year': str(fiscal_year),
                'batch_number': str(batch_num),
                'record_count': str(len(results)),
                'ingestion_timestamp': datetime.utcnow().isoformat()
            }
        )

        s3_path = f"s3://{LANDING_ZONE_BUCKET}/{s3_key}"
        logger.info(f"Saved {len(results)} records to {s3_path}")
        return s3_path

    except ClientError as e:
        logger.error(f"Failed to save batch to S3: {str(e)}")
        raise
