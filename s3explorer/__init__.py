"""
localstack-s3-explorer
======================
CLI and TUI to explore files in a local S3 bucket (Localstack) without
needing the AWS CLI installed.

Localstack setup
----------------
Start Localstack with Docker::

    docker run --rm -p 4566:4566 localstack/localstack

Then create a bucket::

    aws --endpoint-url=http://localhost:4566 s3 mb s3://my-bucket

Or use the ``--mock`` flag to explore sample data without Localstack.

Connecting to Localstack
------------------------
The tool connects to ``http://localhost:4566`` by default.
Override with ``--endpoint`` or the ``LOCALSTACK_ENDPOINT`` env var.

To use with a real boto3 client::

    import boto3
    client = boto3.client(
        "s3",
        endpoint_url="http://localhost:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )

Public API
----------
- :class:`~s3explorer.client.LocalS3Client`  — Localstack S3 wrapper (mockable)
- :class:`~s3explorer.explorer.Explorer`     — browse and download objects
"""

__version__ = "1.0.0"
__author__  = "Jishanahmed AR Shaikh"
__license__ = "MIT"

from s3explorer.client import LocalS3Client   # noqa: F401
from s3explorer.explorer import Explorer      # noqa: F401
