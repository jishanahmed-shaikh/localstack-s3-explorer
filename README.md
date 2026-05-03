<div align="center">

# localstack-s3-explorer

**Browse your local S3 buckets without the AWS CLI.**

An interactive CLI and TUI to explore, search, preview, and download files from a Localstack S3 instance during local cloud development.

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Zero Runtime Deps](https://img.shields.io/badge/Runtime%20Deps-Zero-22c55e?style=flat)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat)](CONTRIBUTING.md)
[![CI](https://github.com/jishanahmed-shaikh/localstack-s3-explorer/actions/workflows/ci.yml/badge.svg)](https://github.com/jishanahmed-shaikh/localstack-s3-explorer/actions)

</div>

---

## Why this exists

You're developing locally with Localstack. You upload some files to a local S3 bucket. Now you want to check what's in there — but you don't want to type `aws --endpoint-url=http://localhost:4566 s3 ls s3://my-bucket/data/2026/` every time. `s3explorer` gives you an interactive browser and simple commands to explore your local buckets instantly.

---

## Install

```bash
# Base (no AWS client — use --mock for testing)
pip install localstack-s3-explorer

# With boto3 for real Localstack usage
pip install "localstack-s3-explorer[aws]"
```

---

## Localstack setup

```bash
# Start Localstack
docker run --rm -p 4566:4566 localstack/localstack

# Create a bucket
aws --endpoint-url=http://localhost:4566 s3 mb s3://my-bucket

# Upload some files
aws --endpoint-url=http://localhost:4566 s3 cp data.parquet s3://my-bucket/data/
```

Localstack accepts any non-empty credentials. The conventional values are:
- `AWS_ACCESS_KEY_ID=test`
- `AWS_SECRET_ACCESS_KEY=test`

---

## Quick start

```bash
# Interactive TUI (arrow keys to navigate)
s3explorer --mock

# List all buckets
s3explorer ls --mock

# List objects in a bucket
s3explorer ls my-bucket --mock

# List objects under a prefix
s3explorer ls my-bucket/data/2026/ --mock

# Download a file
s3explorer get my-bucket/data/file.parquet --output ./local --mock

# Show object metadata
s3explorer info my-bucket/data/file.parquet --mock

# Preview file content
s3explorer preview my-bucket/config/settings.json --mock

# Search for objects
s3explorer search my-bucket json --mock

# Connect to real Localstack
s3explorer ls --endpoint http://localhost:4566
```

---

## Interactive TUI

```
  Localstack S3 Explorer  /

  Buckets

  ↑↓ navigate   Enter open   b back   d download   p preview   / search   q quit

  🪣  dev-data
  🪣  ml-models
  🪣  logs
```

Navigate with arrow keys, press Enter to open a bucket or folder, `d` to download the selected file, `p` to preview, `/` to search, `b` to go back, `q` to quit.

---

## All commands

| Command | Description |
|---------|-------------|
| `s3explorer` | Launch interactive TUI |
| `s3explorer ls` | List all buckets |
| `s3explorer ls BUCKET` | List objects in bucket |
| `s3explorer ls BUCKET/PREFIX` | List objects under prefix |
| `s3explorer get BUCKET/KEY` | Download an object |
| `s3explorer info BUCKET/KEY` | Show object metadata |
| `s3explorer preview BUCKET/KEY` | Preview object content |
| `s3explorer search BUCKET QUERY` | Search by key substring |

## Global flags

| Flag | Description |
|------|-------------|
| `--endpoint URL` | Localstack endpoint (default: `http://localhost:4566`) |
| `--access-key KEY` | AWS access key (default: `test`) |
| `--secret-key KEY` | AWS secret key (default: `test`) |
| `--mock` | Use built-in sample data (no Localstack needed) |
| `--json` | Output as JSON |

---

## Library usage

```python
import boto3
from s3explorer import LocalS3Client, Explorer

# Connect to Localstack
boto_client = boto3.client(
    "s3",
    endpoint_url="http://localhost:4566",
    aws_access_key_id="test",
    aws_secret_access_key="test",
    region_name="us-east-1",
)
client   = LocalS3Client(boto_client)
explorer = Explorer(client)

# List buckets
for bucket in explorer.list_buckets():
    print(bucket.name)

# Browse objects
folders, objects = explorer.list_path("my-bucket", "data/")
for obj in objects:
    print(f"{obj.key}  {obj.size_human()}")

# Download
path = explorer.download("my-bucket", "data/file.parquet", output_dir="./local")

# Preview
print(explorer.preview("my-bucket", "config/settings.json"))
```

---

## Project structure

```
localstack-s3-explorer/
├── s3explorer/
│   ├── __init__.py    # Public API + Localstack setup docs
│   ├── client.py      # LocalS3Client wrapper + MockLocalS3Client
│   ├── explorer.py    # High-level browse, search, download, preview
│   ├── tui.py         # Interactive ANSI TUI with arrow-key navigation
│   └── cli.py         # CLI: ls, get, info, preview, search subcommands
├── tests/
│   └── test_explorer.py  # 25 tests, all run without Localstack
└── pyproject.toml
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues labelled [`good first issue`](https://github.com/jishanahmed-shaikh/localstack-s3-explorer/issues?q=label%3A%22good+first+issue%22) are a great place to start.

---

## License

[MIT](LICENSE) © 2026 [Jishanahmed AR Shaikh](https://github.com/jishanahmed-shaikh)
