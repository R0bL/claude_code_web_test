"""
Unit tests for NIH RePORTER Lambda handler.
"""

import json
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest
import boto3
from moto import mock_s3

# Import handler functions
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../nih_reporter/lambda_function'))
from handler import (
    lambda_handler,
    process_fiscal_year,
    build_request_payload,
    query_api,
    save_batch_to_s3,
    NIHReporterAPIError
)


@pytest.fixture
def mock_env_vars():
    """Set up environment variables for testing."""
    with patch.dict(os.environ, {
        'LANDING_ZONE_BUCKET': 'test-landing-bucket',
        'API_BASE_URL': 'https://api.reporter.nih.gov',
        'RATE_LIMIT_DELAY': '0.1',  # Shorter for tests
        'MAX_RECORDS_PER_REQUEST': '500',
        'MAX_OFFSET': '14999'
    }):
        yield


@pytest.fixture
def s3_setup():
    """Set up mock S3 bucket."""
    with mock_s3():
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.create_bucket(Bucket='test-landing-bucket')
        yield s3


@pytest.fixture
def sample_api_response():
    """Sample API response for testing."""
    return {
        'meta': {
            'total': 2
        },
        'results': [
            {
                'appl_id': 10001,
                'project_num': '1R01CA123456-01',
                'fiscal_year': 2024,
                'project_title': 'Test Project 1',
                'organization': {
                    'org_name': 'Test University',
                    'org_city': 'Boston',
                    'org_state': 'MA'
                },
                'principal_investigators': [
                    {
                        'profile_id': 12345,
                        'first_name': 'John',
                        'last_name': 'Doe',
                        'is_contact_pi': True
                    }
                ],
                'award_amount': 500000
            },
            {
                'appl_id': 10002,
                'project_num': '1R01CA123457-01',
                'fiscal_year': 2024,
                'project_title': 'Test Project 2',
                'organization': {
                    'org_name': 'Test Institute',
                    'org_city': 'New York',
                    'org_state': 'NY'
                },
                'principal_investigators': [
                    {
                        'profile_id': 12346,
                        'first_name': 'Jane',
                        'last_name': 'Smith',
                        'is_contact_pi': True
                    }
                ],
                'award_amount': 750000
            }
        ]
    }


class TestBuildRequestPayload:
    """Tests for build_request_payload function."""

    def test_basic_payload(self):
        """Test basic payload construction."""
        payload = build_request_payload(
            fiscal_year=2024,
            offset=0,
            limit=500
        )

        assert payload['criteria']['fiscal_years'] == [2024]
        assert payload['offset'] == 0
        assert payload['limit'] == 500
        assert 'include_fields' not in payload

    def test_payload_with_include_fields(self):
        """Test payload with include_fields."""
        include_fields = ['project_num', 'project_title', 'award_amount']
        payload = build_request_payload(
            fiscal_year=2024,
            offset=0,
            limit=500,
            include_fields=include_fields
        )

        assert payload['include_fields'] == include_fields

    def test_payload_with_additional_criteria(self):
        """Test payload with additional criteria."""
        additional_criteria = {
            'agencies': ['NCI'],
            'award_amount_range': {'min': 100000}
        }
        payload = build_request_payload(
            fiscal_year=2024,
            offset=0,
            limit=500,
            additional_criteria=additional_criteria
        )

        assert payload['criteria']['fiscal_years'] == [2024]
        assert payload['criteria']['agencies'] == ['NCI']
        assert payload['criteria']['award_amount_range'] == {'min': 100000}


class TestQueryAPI:
    """Tests for query_api function."""

    @patch('handler.requests.post')
    def test_successful_api_call(self, mock_post, sample_api_response):
        """Test successful API call."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_api_response
        mock_post.return_value = mock_response

        payload = {'criteria': {'fiscal_years': [2024]}, 'offset': 0, 'limit': 500}
        result = query_api(payload)

        assert result == sample_api_response
        assert mock_post.call_count == 1

    @patch('handler.requests.post')
    def test_api_rate_limit_retry(self, mock_post, sample_api_response):
        """Test retry on rate limit (429)."""
        # First call returns 429, second succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = sample_api_response

        mock_post.side_effect = [mock_response_429, mock_response_200]

        payload = {'criteria': {'fiscal_years': [2024]}, 'offset': 0, 'limit': 500}
        result = query_api(payload)

        assert result == sample_api_response
        assert mock_post.call_count == 2

    @patch('handler.requests.post')
    def test_api_failure_after_retries(self, mock_post):
        """Test failure after max retries."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response

        payload = {'criteria': {'fiscal_years': [2024]}, 'offset': 0, 'limit': 500}

        with pytest.raises(NIHReporterAPIError):
            query_api(payload, max_retries=3)

        assert mock_post.call_count == 3

    @patch('handler.requests.post')
    def test_api_timeout(self, mock_post):
        """Test timeout handling."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        payload = {'criteria': {'fiscal_years': [2024]}, 'offset': 0, 'limit': 500}

        with pytest.raises(NIHReporterAPIError) as excinfo:
            query_api(payload, max_retries=2)

        assert 'timed out' in str(excinfo.value).lower()
        assert mock_post.call_count == 2


class TestSaveBatchToS3:
    """Tests for save_batch_to_s3 function."""

    def test_save_batch(self, s3_setup, mock_env_vars, sample_api_response):
        """Test saving batch to S3."""
        results = sample_api_response['results']

        s3_path = save_batch_to_s3(
            results=results,
            fiscal_year=2024,
            batch_num=0
        )

        # Verify S3 path format
        assert s3_path.startswith('s3://test-landing-bucket/nih_reporter/projects/')
        assert 'FY2024' in s3_path
        assert 'batch0000' in s3_path

        # Verify file was uploaded
        bucket_name = 'test-landing-bucket'
        s3_key = s3_path.replace(f's3://{bucket_name}/', '')

        response = s3_setup.get_object(Bucket=bucket_name, Key=s3_key)
        content = response['Body'].read().decode('utf-8')

        # Verify JSONL format (one JSON per line)
        lines = content.strip().split('\n')
        assert len(lines) == 2

        # Verify each line is valid JSON with metadata
        for line in lines:
            record = json.loads(line)
            assert '_ingestion_metadata' in record
            assert record['_ingestion_metadata']['fiscal_year'] == 2024

        # Verify metadata
        metadata = response['Metadata']
        assert metadata['fiscal_year'] == '2024'
        assert metadata['batch_number'] == '0'
        assert metadata['record_count'] == '2'


class TestProcessFiscalYear:
    """Tests for process_fiscal_year function."""

    @patch('handler.query_api')
    @patch('handler.save_batch_to_s3')
    @patch('handler.time.sleep')
    def test_process_single_batch(
        self,
        mock_sleep,
        mock_save,
        mock_query,
        mock_env_vars,
        sample_api_response
    ):
        """Test processing single batch."""
        mock_query.return_value = sample_api_response
        mock_save.return_value = 's3://test-bucket/test.jsonl'

        files, count = process_fiscal_year(fiscal_year=2024)

        assert len(files) == 1
        assert count == 2
        assert mock_query.call_count == 1
        assert mock_save.call_count == 1

    @patch('handler.query_api')
    @patch('handler.save_batch_to_s3')
    @patch('handler.time.sleep')
    def test_process_multiple_batches(
        self,
        mock_sleep,
        mock_save,
        mock_query,
        mock_env_vars
    ):
        """Test processing multiple batches with pagination."""
        # First batch: 500 results, total 1000
        batch1 = {
            'meta': {'total': 1000},
            'results': [{'appl_id': i} for i in range(500)]
        }

        # Second batch: 500 results, total 1000
        batch2 = {
            'meta': {'total': 1000},
            'results': [{'appl_id': i} for i in range(500, 1000)]
        }

        mock_query.side_effect = [batch1, batch2]
        mock_save.return_value = 's3://test-bucket/test.jsonl'

        files, count = process_fiscal_year(fiscal_year=2024)

        assert len(files) == 2
        assert count == 1000
        assert mock_query.call_count == 2
        assert mock_save.call_count == 2


class TestLambdaHandler:
    """Tests for main lambda_handler function."""

    @patch('handler.process_fiscal_year')
    def test_handler_success(self, mock_process, mock_env_vars):
        """Test successful handler execution."""
        mock_process.return_value = (['s3://bucket/file1.jsonl'], 100)

        event = {
            'fiscal_years': [2024, 2023]
        }
        context = {}

        result = lambda_handler(event, context)

        assert result['status'] == 'success'
        assert result['total_records'] == 200
        assert len(result['files_processed']) == 2
        assert mock_process.call_count == 2

    @patch('handler.process_fiscal_year')
    def test_handler_partial_success(self, mock_process, mock_env_vars):
        """Test handler with partial success."""
        # First call succeeds, second fails
        mock_process.side_effect = [
            (['s3://bucket/file1.jsonl'], 100),
            Exception('API Error')
        ]

        event = {
            'fiscal_years': [2024, 2023]
        }
        context = {}

        result = lambda_handler(event, context)

        assert result['status'] == 'partial_success'
        assert result['total_records'] == 100
        assert len(result['errors']) == 1
        assert 'API Error' in result['errors'][0]

    def test_handler_default_fiscal_year(self, mock_env_vars):
        """Test handler uses current year by default."""
        with patch('handler.process_fiscal_year') as mock_process:
            mock_process.return_value = ([], 0)

            event = {}
            context = {}

            result = lambda_handler(event, context)

            # Should use current year
            current_year = datetime.now().year
            call_args = mock_process.call_args_list[0][1]
            assert call_args['fiscal_year'] == current_year

    def test_handler_missing_bucket_env(self):
        """Test handler fails gracefully when env var missing."""
        with patch.dict(os.environ, {}, clear=True):
            event = {'fiscal_years': [2024]}
            context = {}

            result = lambda_handler(event, context)

            assert result['status'] == 'failed'
            assert 'LANDING_ZONE_BUCKET' in result['error']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
