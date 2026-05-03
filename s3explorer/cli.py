"""
Command-line interface for localstack-s3-explorer.

Usage
-----
    s3explorer                          # interactive TUI
    s3explorer ls                       # list buckets
    s3explorer ls my-bucket             # list objects in bucket
    s3explorer ls my-bucket/data/       # list objects under prefix
    s3explorer get my-bucket/data/file  # download a file
    s3explorer info my-bucket/data/file # show object metadata
    s3explorer preview my-bucket/file   # preview file content
    s3explorer search my-bucket query   # search for objects
    s3explorer --mock                   # use built-in sample data
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import urlparse

from s3explorer import __version__
from s3explorer.client import LocalS3Client, MockLocalS3Client
from s3explorer.explorer import Explorer


_DEFAULT_ENDPOINT = os.environ.get("LOCALSTACK_ENDPOINT", "http://localhost:4566")

_GREEN = "\033[92m"
_CYAN  = "\033[96m"
_BOLD  = "\033[1m"
_DIM   = "\033[2m"
_RESET = "\033[0m"


def _parse_path(path: str) -> tuple:
    """Parse 'bucket/prefix' or 's3://bucket/prefix' into (bucket, key)."""
    if path.startswith("s3://"):
        parsed = urlparse(path)
        return parsed.netloc, parsed.path.lstrip("/")
    if "/" in path:
        parts = path.split("/", 1)
        return parts[0], parts[1]
    return path, ""


def _build_client(args: argparse.Namespace) -> LocalS3Client:
    """Build a LocalS3Client from CLI args."""
    if args.mock:
        return LocalS3Client(MockLocalS3Client())
    try:
        import boto3  # type: ignore
        session = boto3.Session(
            profile_name=getattr(args, "profile", None),
            region_name=getattr(args, "region", "us-east-1"),
        )
        boto_client = session.client(
            "s3",
            endpoint_url=args.endpoint,
            aws_access_key_id=getattr(args, "access_key", "test") or "test",
            aws_secret_access_key=getattr(args, "secret_key", "test") or "test",
        )
        return LocalS3Client(boto_client)
    except ImportError:
        print(
            "Error: boto3 is not installed.\n"
            "Install it with:  pip install 'localstack-s3-explorer[aws]'\n"
            "Or use --mock to explore sample data without Localstack.",
            file=sys.stderr,
        )
        sys.exit(1)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="s3explorer",
        description=(
            "Explore files in a local S3 bucket (Localstack) without the AWS CLI.\n\n"
            "Localstack setup:\n"
            "  docker run --rm -p 4566:4566 localstack/localstack\n\n"
            "Credentials: Localstack accepts any non-empty values.\n"
            "  Default: access_key=test, secret_key=test\n\n"
            "Use --mock to explore sample data without Localstack running."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global flags
    parser.add_argument("--endpoint", default=_DEFAULT_ENDPOINT,
                        help=f"Localstack endpoint URL (default: {_DEFAULT_ENDPOINT})")
    parser.add_argument("--access-key", default=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
                        help="AWS access key (default: test)")
    parser.add_argument("--secret-key", default=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
                        help="AWS secret key (default: test)")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--profile", default=None, help="AWS profile name")
    parser.add_argument("--mock", action="store_true",
                        help="Use built-in mock data (no Localstack needed)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--version", "-V", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ls
    ls_p = sub.add_parser("ls", help="List buckets or objects")
    ls_p.add_argument("path", nargs="?", default="",
                      help="bucket or bucket/prefix to list")

    # get
    get_p = sub.add_parser("get", help="Download an object")
    get_p.add_argument("path", help="bucket/key to download")
    get_p.add_argument("--output", "-o", default=".", help="Output directory (default: .)")
    get_p.add_argument("--flat", action="store_true",
                       help="Write only the filename, not the full key structure")

    # info
    info_p = sub.add_parser("info", help="Show object metadata")
    info_p.add_argument("path", help="bucket/key")

    # preview
    prev_p = sub.add_parser("preview", help="Preview object content")
    prev_p.add_argument("path", help="bucket/key")
    prev_p.add_argument("--bytes", type=int, default=512, help="Max bytes to preview (default: 512)")

    # search
    srch_p = sub.add_parser("search", help="Search for objects by key substring")
    srch_p.add_argument("bucket", help="Bucket to search")
    srch_p.add_argument("query", help="Search query (case-insensitive substring)")
    srch_p.add_argument("--prefix", default="", help="Limit search to this prefix")

    args = parser.parse_args(argv)
    use_color = sys.stdout.isatty() and not args.json

    client   = _build_client(args)
    explorer = Explorer(client)

    # No subcommand — launch TUI
    if not args.command:
        from s3explorer.tui import run_tui
        run_tui(client)
        return

    if args.command == "ls":
        if not args.path:
            buckets = explorer.list_buckets()
            if args.json:
                print(json.dumps([{"name": b.name, "created": b.creation_date} for b in buckets]))
            else:
                print()
                for b in buckets:
                    c = _CYAN if use_color else ""
                    r = _RESET if use_color else ""
                    print(f"  {c}🪣  {b.name}{r}")
                print()
        else:
            bucket, prefix = _parse_path(args.path)
            folders, objects = explorer.list_path(bucket, prefix)
            if args.json:
                print(json.dumps({
                    "folders": folders,
                    "objects": [{"key": o.key, "size": o.size, "last_modified": o.last_modified} for o in objects],
                }))
            else:
                print()
                for f in folders:
                    name = f.rstrip("/").rsplit("/", 1)[-1]
                    d = _DIM if use_color else ""
                    r = _RESET if use_color else ""
                    print(f"  {d}📁  {name}/{r}")
                for o in objects:
                    g = _GREEN if use_color else ""
                    r = _RESET if use_color else ""
                    print(f"  📄  {g}{o.name}{r}  {o.size_human():>10}  {o.last_modified}")
                print()

    elif args.command == "get":
        bucket, key = _parse_path(args.path)
        path = explorer.download(bucket, key, output_dir=args.output,
                                 preserve_structure=not args.flat)
        print(f"  Downloaded: {path}")

    elif args.command == "info":
        bucket, key = _parse_path(args.path)
        info = explorer.get_info(bucket, key)
        if args.json:
            print(json.dumps({
                "key": info.key, "size": info.size,
                "last_modified": info.last_modified,
                "etag": info.etag, "content_type": info.content_type,
            }))
        else:
            print(f"\n  Key:          {info.key}")
            print(f"  Size:         {info.size_human()} ({info.size} bytes)")
            print(f"  Last modified:{info.last_modified}")
            print(f"  ETag:         {info.etag}")
            print(f"  Content-Type: {info.content_type or 'unknown'}")
            print()

    elif args.command == "preview":
        bucket, key = _parse_path(args.path)
        text = explorer.preview(bucket, key, max_bytes=args.bytes)
        print(f"\n  Preview: {key}\n")
        print(text)
        print()

    elif args.command == "search":
        results = explorer.search(args.bucket, args.query, prefix=args.prefix)
        if args.json:
            print(json.dumps([{"key": o.key, "size": o.size} for o in results]))
        else:
            print(f"\n  {len(results)} result(s) for '{args.query}' in {args.bucket}:\n")
            for o in results:
                g = _GREEN if use_color else ""
                r = _RESET if use_color else ""
                print(f"  {g}{o.key}{r}  {o.size_human()}")
            print()


if __name__ == "__main__":
    main()
