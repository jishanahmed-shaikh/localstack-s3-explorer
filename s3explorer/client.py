"""
Localstack S3 client wrapper.

Wraps the S3 API into a minimal interface used by :class:`~s3explorer.explorer.Explorer`.
Works with Localstack, real AWS S3, or the built-in :class:`MockLocalS3Client`.

Localstack credentials
----------------------
Localstack accepts any non-empty credentials.  The conventional values are::

    aws_access_key_id     = "test"
    aws_secret_access_key = "test"
    region_name           = "us-east-1"
    endpoint_url          = "http://localhost:4566"

Production usage::

    import boto3
    boto_client = boto3.client(
        "s3",
        endpoint_url="http://localhost:4566",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    client = LocalS3Client(boto_client)
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class BucketInfo:
    """Metadata for an S3 bucket.

    Attributes
    ----------
    name:
        Bucket name.
    creation_date:
        ISO-8601 creation date string.
    """

    name: str
    creation_date: str = ""


@dataclass
class ObjectInfo:
    """Metadata for a single S3 object.

    Attributes
    ----------
    key:
        Full object key (e.g. ``"data/sales.parquet"``).
    size:
        Object size in bytes.
    last_modified:
        ISO-8601 last-modified timestamp string.
    etag:
        ETag hash string.
    content_type:
        MIME type of the object.
    """

    key: str
    size: int
    last_modified: str = ""
    etag: str = ""
    content_type: str = ""

    @property
    def name(self) -> str:
        """Filename portion of the key (last path segment)."""
        return self.key.rstrip("/").rsplit("/", 1)[-1]

    @property
    def is_folder(self) -> bool:
        """True if this object represents a virtual folder (key ends with /)."""
        return self.key.endswith("/")

    def size_human(self) -> str:
        """Return size as a human-readable string."""
        n = self.size
        if n < 1024:
            return f"{n}B"
        if n < 1024 ** 2:
            return f"{n / 1024:.1f}KB"
        if n < 1024 ** 3:
            return f"{n / 1024 ** 2:.1f}MB"
        return f"{n / 1024 ** 3:.2f}GB"


class LocalS3Client:
    """Thin wrapper around a boto3 S3 client configured for Localstack.

    Parameters
    ----------
    boto_client:
        A ``boto3`` S3 client pointed at Localstack (or real AWS),
        or a :class:`MockLocalS3Client` for testing.
    """

    def __init__(self, boto_client: Any) -> None:
        self._client = boto_client

    def list_buckets(self) -> List[BucketInfo]:
        """List all buckets.

        Returns
        -------
        List[BucketInfo]
            All buckets visible to the configured credentials.
        """
        resp = self._client.list_buckets()
        return [
            BucketInfo(
                name=b["Name"],
                creation_date=str(b.get("CreationDate", "")),
            )
            for b in resp.get("Buckets", [])
        ]

    def list_objects(
        self,
        bucket: str,
        prefix: str = "",
        delimiter: str = "/",
    ) -> tuple:
        """List objects and common prefixes (virtual folders) in *bucket*.

        Parameters
        ----------
        bucket:
            Bucket name.
        prefix:
            Key prefix to list under (e.g. ``"data/"``).
        delimiter:
            Delimiter for virtual folder grouping (default: ``"/"``).

        Returns
        -------
        tuple
            ``(objects, prefixes)`` where *objects* is a list of
            :class:`ObjectInfo` and *prefixes* is a list of prefix strings.
        """
        resp = self._client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter=delimiter,
        )
        objects = [
            ObjectInfo(
                key=obj["Key"],
                size=obj.get("Size", 0),
                last_modified=str(obj.get("LastModified", "")),
                etag=obj.get("ETag", "").strip('"'),
            )
            for obj in resp.get("Contents", [])
            if obj["Key"] != prefix  # skip the prefix itself
        ]
        prefixes = [
            cp["Prefix"]
            for cp in resp.get("CommonPrefixes", [])
        ]
        return objects, prefixes

    def get_object_info(self, bucket: str, key: str) -> ObjectInfo:
        """Get metadata for a single object via HeadObject.

        Parameters
        ----------
        bucket:
            Bucket name.
        key:
            Object key.

        Returns
        -------
        ObjectInfo
            Object metadata.
        """
        resp = self._client.head_object(Bucket=bucket, Key=key)
        return ObjectInfo(
            key=key,
            size=resp.get("ContentLength", 0),
            last_modified=str(resp.get("LastModified", "")),
            etag=resp.get("ETag", "").strip('"'),
            content_type=resp.get("ContentType", ""),
        )

    def download_object(self, bucket: str, key: str) -> bytes:
        """Download an object and return its content as bytes.

        Parameters
        ----------
        bucket:
            Bucket name.
        key:
            Object key.

        Returns
        -------
        bytes
            Raw object content.
        """
        try:
            resp = self._client.get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:
            raise RuntimeError(f"Failed to download s3://{bucket}/{key}: {exc}") from exc

    def create_bucket(self, bucket: str) -> None:
        """Create a bucket (useful for Localstack setup).

        Parameters
        ----------
        bucket:
            Bucket name to create.
        """
        self._client.create_bucket(Bucket=bucket)

    def put_object(self, bucket: str, key: str, data: bytes) -> None:
        """Upload an object (useful for Localstack setup and testing).

        Parameters
        ----------
        bucket:
            Bucket name.
        key:
            Object key.
        data:
            Raw bytes to upload.
        """
        self._client.put_object(Bucket=bucket, Key=key, Body=data)

    def copy_object(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> None:
        """Copy an object from one bucket/prefix to another.

        Parameters
        ----------
        src_bucket:
            Source bucket name.
        src_key:
            Source object key.
        dst_bucket:
            Destination bucket name.
        dst_key:
            Destination object key.
        """
        try:
            self._client.copy_object(
                Bucket=dst_bucket,
                Key=dst_key,
                CopySource={"Bucket": src_bucket, "Key": src_key},
                MetadataDirective="COPY",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to copy s3://{src_bucket}/{src_key} to s3://{dst_bucket}/{dst_key}: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Mock client — identical interface, no Localstack required
# ---------------------------------------------------------------------------

class MockLocalS3Client:
    """In-memory Localstack S3 mock for unit testing.

    Pre-loaded with realistic sample buckets and objects.
    Swapping this for a real boto3 client requires zero code changes::

        import boto3
        real = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        client = LocalS3Client(real)

    Parameters
    ----------
    buckets:
        Dict mapping bucket name to dict of ``{key: bytes}``.
        If ``None``, a default set of sample data is used.
    """

    _DEFAULT: Dict[str, Dict[str, bytes]] = {
        "dev-data": {
            "raw/2026/01/events.parquet":    b"PAR1" + b"\x00" * 128,
            "raw/2026/01/users.json":        b'[{"id":1,"name":"Alice"},{"id":2,"name":"Bob"}]',
            "raw/2026/02/events.parquet":    b"PAR1" + b"\x00" * 96,
            "processed/summary.csv":         b"date,count\n2026-01-01,42\n2026-01-02,38\n",
            "processed/report.html":         b"<html><body>Report</body></html>",
            "config/settings.json":          b'{"env":"local","debug":true}',
        },
        "ml-models": {
            "v1/model.pkl":                  b"\x80\x04\x95" + b"\x00" * 64,
            "v1/metadata.json":              b'{"version":"1.0","accuracy":0.94}',
            "v2/model.pkl":                  b"\x80\x04\x95" + b"\x00" * 80,
            "v2/metadata.json":              b'{"version":"2.0","accuracy":0.97}',
        },
        "logs": {
            "app/2026-04-30.log":            b"INFO started\nWARN slow query\nERROR timeout\n",
            "app/2026-05-01.log":            b"INFO started\nINFO healthy\n",
        },
    }

    def __init__(self, buckets: Optional[Dict[str, Dict[str, bytes]]] = None) -> None:
        import copy
        self._buckets: Dict[str, Dict[str, bytes]] = (
            copy.deepcopy(buckets) if buckets is not None
            else copy.deepcopy(self._DEFAULT)
        )

    def list_buckets(self) -> Dict:
        return {
            "Buckets": [
                {"Name": name, "CreationDate": "2026-01-01T00:00:00+00:00"}
                for name in self._buckets
            ]
        }

    def list_objects_v2(self, Bucket: str, Prefix: str = "", Delimiter: str = "/") -> Dict:
        objects_raw = self._buckets.get(Bucket, {})
        contents = []
        common_prefixes = set()

        for key, data in objects_raw.items():
            if not key.startswith(Prefix):
                continue
            remainder = key[len(Prefix):]
            if Delimiter and Delimiter in remainder:
                # Virtual folder
                folder = Prefix + remainder.split(Delimiter)[0] + Delimiter
                common_prefixes.add(folder)
            else:
                contents.append({
                    "Key": key,
                    "Size": len(data),
                    "LastModified": "2026-04-30T12:00:00+00:00",
                    "ETag": f'"{hash(data) & 0xFFFFFFFF:08x}"',
                })

        return {
            "Contents": contents,
            "CommonPrefixes": [{"Prefix": p} for p in sorted(common_prefixes)],
        }

    def head_object(self, Bucket: str, Key: str) -> Dict:
        data = self._buckets.get(Bucket, {}).get(Key)
        if data is None:
            raise KeyError(f"NoSuchKey: {Key}")
        return {
            "ContentLength": len(data),
            "LastModified": "2026-04-30T12:00:00+00:00",
            "ETag": f'"{hash(data) & 0xFFFFFFFF:08x}"',
            "ContentType": "application/octet-stream",
        }

    def get_object(self, Bucket: str, Key: str) -> Dict:
        data = self._buckets.get(Bucket, {}).get(Key)
        if data is None:
            raise KeyError(f"NoSuchKey: {Key}")
        return {"Body": io.BytesIO(data)}

    def create_bucket(self, Bucket: str) -> None:
        self._buckets.setdefault(Bucket, {})

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self._buckets.setdefault(Bucket, {})[Key] = Body
