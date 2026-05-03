"""
Explorer — browse and operate on Localstack S3 buckets.

Provides a high-level API for listing, navigating, downloading,
and inspecting objects.  Used by both the CLI and the TUI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

from s3explorer.client import BucketInfo, LocalS3Client, ObjectInfo


class Explorer:
    """Browse and operate on S3 buckets via a :class:`~s3explorer.client.LocalS3Client`.

    Parameters
    ----------
    client:
        A :class:`~s3explorer.client.LocalS3Client` instance.
    """

    def __init__(self, client: LocalS3Client) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # Bucket operations
    # ------------------------------------------------------------------

    def list_buckets(self) -> List[BucketInfo]:
        """Return all buckets.

        Returns
        -------
        List[BucketInfo]
            All buckets sorted by name.
        """
        return sorted(self.client.list_buckets(), key=lambda b: b.name)

    # ------------------------------------------------------------------
    # Object browsing
    # ------------------------------------------------------------------

    def list_path(
        self,
        bucket: str,
        prefix: str = "",
    ) -> Tuple[List[str], List[ObjectInfo]]:
        """List virtual folders and objects at *prefix* in *bucket*.

        Parameters
        ----------
        bucket:
            Bucket name.
        prefix:
            Current path prefix (e.g. ``"data/2026/"``).

        Returns
        -------
        tuple
            ``(folders, objects)`` where *folders* is a list of prefix
            strings and *objects* is a list of :class:`~s3explorer.client.ObjectInfo`.
        """
        objects, prefixes = self.client.list_objects(bucket, prefix=prefix, delimiter="/")
        return prefixes, objects

    def search(
        self,
        bucket: str,
        query: str,
        prefix: str = "",
    ) -> List[ObjectInfo]:
        """Search for objects whose key contains *query*.

        Parameters
        ----------
        bucket:
            Bucket name.
        query:
            Case-insensitive substring to search for.
        prefix:
            Limit search to this prefix.

        Returns
        -------
        List[ObjectInfo]
            Matching objects.
        """
        # List all objects recursively (no delimiter)
        objects, _ = self.client.list_objects(bucket, prefix=prefix, delimiter="")
        q = query.lower()
        return [o for o in objects if q in o.key.lower()]

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(
        self,
        bucket: str,
        key: str,
        output_dir: str = ".",
        preserve_structure: bool = True,
    ) -> str:
        """Download an object to a local file.

        Parameters
        ----------
        bucket:
            Bucket name.
        key:
            Object key to download.
        output_dir:
            Local directory to write the file into.
        preserve_structure:
            If ``True``, mirror the S3 key structure under *output_dir*.
            If ``False``, write only the filename.

        Returns
        -------
        str
            Path to the downloaded file.
        """
        data = self.client.download_object(bucket, key)

        if preserve_structure:
            local_path = Path(output_dir) / key
        else:
            local_path = Path(output_dir) / Path(key).name

        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        return str(local_path)

    def download_prefix(
        self,
        bucket: str,
        prefix: str,
        output_dir: str = ".",
    ) -> List[str]:
        """Download all objects under *prefix* recursively.

        Parameters
        ----------
        bucket:
            Bucket name.
        prefix:
            Key prefix to download.
        output_dir:
            Local output directory.

        Returns
        -------
        List[str]
            Paths to all downloaded files.
        """
        objects, _ = self.client.list_objects(bucket, prefix=prefix, delimiter="")
        downloaded = []
        for obj in objects:
            if not obj.is_folder:
                path = self.download(bucket, obj.key, output_dir=output_dir)
                downloaded.append(path)
        return downloaded

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def get_info(self, bucket: str, key: str) -> ObjectInfo:
        """Get detailed metadata for a single object.

        Parameters
        ----------
        bucket:
            Bucket name.
        key:
            Object key.

        Returns
        -------
        ObjectInfo
            Object metadata including size, ETag, and content type.
        """
        return self.client.get_object_info(bucket, key)

    def preview(self, bucket: str, key: str, max_bytes: int = 512) -> str:
        """Return a text preview of an object's content.

        For binary files, returns a hex dump of the first bytes.
        For text files (JSON, CSV, log, etc.), returns the raw text.

        Parameters
        ----------
        bucket:
            Bucket name.
        key:
            Object key.
        max_bytes:
            Maximum bytes to read for the preview.

        Returns
        -------
        str
            Preview string.
        """
        data = self.client.download_object(bucket, key)[:max_bytes]
        ext  = os.path.splitext(key)[1].lower()

        text_exts = {".json", ".csv", ".txt", ".log", ".md", ".html", ".xml", ".yaml", ".yml", ".toml"}
        if ext in text_exts:
            try:
                return data.decode("utf-8", errors="replace")
            except Exception:
                pass

        # Hex dump for binary files
        lines = []
        for i in range(0, min(len(data), 64), 16):
            chunk = data[i:i + 16]
            hex_part  = " ".join(f"{b:02x}" for b in chunk)
            text_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"  {i:04x}  {hex_part:<48}  {text_part}")
        return "\n".join(lines)
