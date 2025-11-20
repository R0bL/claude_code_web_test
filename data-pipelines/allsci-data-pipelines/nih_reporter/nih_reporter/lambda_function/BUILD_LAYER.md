# Building Lambda Layer

To build the Lambda layer for the NIH Reporter pipeline:

```bash
cd nih_reporter/lambda_function

# Create python directory for layer
mkdir -p python

# Install dependencies
pip install requests -t python/

# Create layer zip
zip -r layer.zip python/

# Clean up
rm -rf python/
```

## Dependencies

The layer includes:
- `requests` - For HTTP calls to NIH RePORTER API

## Notes

- The layer must be rebuilt whenever requirements.txt changes
- Compatible with Python 3.11 runtime
- Lambda layers are referenced in `lambda_app_construct.py`

