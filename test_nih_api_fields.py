#!/usr/bin/env python3
"""
Test script to verify which fields are returned by NIH Reporter API v2
and specifically check if clinical_trials field exists in the response.
"""

import requests
import json
from pprint import pprint

API_BASE_URL = "https://api.reporter.nih.gov/v2/projects/search"

def test_api_fields():
    """Query API and show all available fields in response."""

    # Simple query for recent projects
    payload = {
        "criteria": {
            "fiscal_years": [2024]
        },
        "offset": 0,
        "limit": 5  # Just get 5 records to examine structure
    }

    print("Testing NIH Reporter API v2...")
    print(f"URL: {API_BASE_URL}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")

    try:
        response = requests.post(
            API_BASE_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        print(f"Status Code: {response.status_code}\n")

        if response.status_code == 200:
            data = response.json()

            print(f"Total records available: {data.get('meta', {}).get('total', 0)}")
            print(f"Records returned: {len(data.get('results', []))}\n")

            if data.get('results'):
                sample_project = data['results'][0]

                print("="*80)
                print("ALL FIELDS IN API RESPONSE:")
                print("="*80)
                for field in sorted(sample_project.keys()):
                    field_type = type(sample_project[field]).__name__
                    sample_value = sample_project[field]

                    # Truncate long values
                    if isinstance(sample_value, str) and len(sample_value) > 50:
                        sample_value = sample_value[:50] + "..."
                    elif isinstance(sample_value, list):
                        sample_value = f"[array with {len(sample_value)} items]"
                    elif isinstance(sample_value, dict):
                        sample_value = f"{{dict with {len(sample_value)} keys}}"

                    print(f"  {field:30s} ({field_type:10s}) = {sample_value}")

                print("\n" + "="*80)
                print("CHECKING FOR SPECIFIC FIELDS:")
                print("="*80)

                # Check for specific fields we care about
                fields_to_check = [
                    'clinical_trials',
                    'publications',
                    'principal_investigators',
                    'program_officers',
                    'spending_categories',
                    'terms'
                ]

                for field in fields_to_check:
                    if field in sample_project:
                        value = sample_project[field]
                        print(f"✓ {field:30s} EXISTS")
                        if isinstance(value, list):
                            print(f"  → Array with {len(value)} items")
                            if value:
                                print(f"  → First item: {json.dumps(value[0], indent=6)}")
                        else:
                            print(f"  → Value: {value}")
                    else:
                        print(f"✗ {field:30s} NOT FOUND")

                print("\n" + "="*80)
                print("SAMPLE PROJECT (FULL JSON):")
                print("="*80)
                print(json.dumps(sample_project, indent=2))

        else:
            print(f"Error: {response.status_code}")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False

    return True

if __name__ == "__main__":
    test_api_fields()
