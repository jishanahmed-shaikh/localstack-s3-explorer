"""Tests for localstack-s3-explorer."""

import os
import tempfile

import pytest

from s3explorer.client import LocalS3Client, MockLocalS3Client, ObjectInfo, BucketInfo
from s3explorer.explorer import Explorer
from s3explorer.cli import _parse_path


# ---------------------------------------------------------------------------
# MockLocalS3Client tests
# ---------------------------------------------------------------------------

class TestMockClient:
    def _client(self):
        return LocalS3Client(MockLocalS3Client())

    def test_list_buckets_returns_buckets(self):
        client = self._client()
        buckets = client.list_buckets()
        assert len(buckets) >= 1
        assert all(isinstance(b, BucketInfo) for b in buckets)

    def test_list_buckets_names(self):
        client = self._client()
        names = [b.name for b in client.list_buckets()]
        assert "dev-data" in names
        assert "ml-models" in names

    def test_list_objects_returns_objects(self):
        client = self._client()
        objects, prefixes = client.list_objects("dev-data")
        assert len(objects) + len(prefixes) > 0

    def test_list_objects_with_prefix(self):
        client = self._client()
        objects, _ = client.list_objects("dev-data", prefix="raw/", delimiter="")
        assert all(o.key.startswith("raw/") for o in objects)

    def test_list_objects_delimiter_returns_folders(self):
        client = self._client()
        _, prefixes = client.list_objects("dev-data", prefix="", delimiter="/")
        assert len(prefixes) > 0

    def test_download_returns_bytes(self):
        client = self._client()
        data = client.download_object("dev-data", "config/settings.json")
        assert isinstance(data, bytes)
        assert b"local" in data

    def test_download_missing_key_raises(self):
        client = self._client()
        with pytest.raises(RuntimeError):
            client.download_object("dev-data", "nonexistent/key.txt")

    def test_head_object_returns_info(self):
        client = self._client()
        info = client.get_object_info("dev-data", "config/settings.json")
        assert isinstance(info, ObjectInfo)
        assert info.size > 0

    def test_put_and_get_object(self):
        mock = MockLocalS3Client()
        mock.create_bucket("test-bucket")
        mock.put_object("test-bucket", "hello.txt", b"hello world")
        client = LocalS3Client(mock)
        data = client.download_object("test-bucket", "hello.txt")
        assert data == b"hello world"

    def test_custom_buckets(self):
        custom = {"my-bucket": {"file.txt": b"content"}}
        mock   = MockLocalS3Client(buckets=custom)
        client = LocalS3Client(mock)
        buckets = client.list_buckets()
        assert len(buckets) == 1
        assert buckets[0].name == "my-bucket"

    def test_copy_object(self):
        mock = MockLocalS3Client()
        client = LocalS3Client(mock)
        # Copy an object between buckets
        client.copy_object("dev-data", "config/settings.json", "dev-data", "backup/settings.json")
        # Verify the copy exists
        data = client.download_object("dev-data", "backup/settings.json")
        assert data == b'{"env":"local","debug":true}'


# ---------------------------------------------------------------------------
# Explorer tests
# ---------------------------------------------------------------------------

class TestExplorer:
    def _explorer(self):
        return Explorer(LocalS3Client(MockLocalS3Client()))

    def test_list_buckets_sorted(self):
        exp = self._explorer()
        buckets = exp.list_buckets()
        names = [b.name for b in buckets]
        assert names == sorted(names)

    def test_list_path_root(self):
        exp = self._explorer()
        folders, objects = exp.list_path("dev-data", "")
        assert len(folders) + len(objects) > 0

    def test_list_path_prefix(self):
        exp = self._explorer()
        folders, objects = exp.list_path("dev-data", "raw/")
        # Should see 2026/ folder
        assert any("2026" in f for f in folders)

    def test_search_finds_results(self):
        exp = self._explorer()
        results = exp.search("dev-data", "json")
        assert len(results) > 0
        assert all("json" in o.key for o in results)

    def test_search_case_insensitive(self):
        exp = self._explorer()
        results_lower = exp.search("dev-data", "json")
        results_upper = exp.search("dev-data", "JSON")
        assert len(results_lower) == len(results_upper)

    def test_search_no_results(self):
        exp = self._explorer()
        results = exp.search("dev-data", "zzznomatch")
        assert results == []

    def test_download_creates_file(self):
        exp = self._explorer()
        with tempfile.TemporaryDirectory() as d:
            path = exp.download("dev-data", "config/settings.json", output_dir=d)
            assert os.path.exists(path)
            assert open(path, "rb").read() == b'{"env":"local","debug":true}'

    def test_download_flat_mode(self):
        exp = self._explorer()
        with tempfile.TemporaryDirectory() as d:
            path = exp.download("dev-data", "config/settings.json",
                                output_dir=d, preserve_structure=False)
            assert os.path.basename(path) == "settings.json"

    def test_download_prefix(self):
        exp = self._explorer()
        with tempfile.TemporaryDirectory() as d:
            paths = exp.download_prefix("dev-data", "config/", output_dir=d)
            assert len(paths) >= 1

    def test_preview_text_file(self):
        exp = self._explorer()
        preview = exp.preview("dev-data", "config/settings.json")
        assert "local" in preview

    def test_preview_binary_file(self):
        exp = self._explorer()
        preview = exp.preview("ml-models", "v1/model.pkl")
        # Binary files get hex dump
        assert "0000" in preview

    def test_get_info(self):
        exp = self._explorer()
        info = exp.get_info("dev-data", "config/settings.json")
        assert info.key == "config/settings.json"
        assert info.size > 0


# ---------------------------------------------------------------------------
# ObjectInfo tests
# ---------------------------------------------------------------------------

class TestObjectInfo:
    def test_name_property(self):
        obj = ObjectInfo(key="data/2026/file.parquet", size=100)
        assert obj.name == "file.parquet"

    def test_is_folder_false(self):
        obj = ObjectInfo(key="data/file.txt", size=10)
        assert obj.is_folder is False

    def test_is_folder_true(self):
        obj = ObjectInfo(key="data/folder/", size=0)
        assert obj.is_folder is True

    def test_size_human_bytes(self):
        obj = ObjectInfo(key="f", size=512)
        assert obj.size_human() == "512B"

    def test_size_human_kb(self):
        obj = ObjectInfo(key="f", size=2048)
        assert "KB" in obj.size_human()

    def test_size_human_mb(self):
        obj = ObjectInfo(key="f", size=2 * 1024 * 1024)
        assert "MB" in obj.size_human()


# ---------------------------------------------------------------------------
# CLI helper tests
# ---------------------------------------------------------------------------

class TestParsePath:
    def test_bucket_only(self):
        bucket, key = _parse_path("my-bucket")
        assert bucket == "my-bucket"
        assert key == ""

    def test_bucket_slash_key(self):
        bucket, key = _parse_path("my-bucket/data/file.json")
        assert bucket == "my-bucket"
        assert key == "data/file.json"

    def test_s3_url(self):
        bucket, key = _parse_path("s3://my-bucket/data/file.json")
        assert bucket == "my-bucket"
        assert key == "data/file.json"


# ---------------------------------------------------------------------------
# Copy tests
# ---------------------------------------------------------------------------

class TestCopy:
    def _explorer(self):
        return Explorer(LocalS3Client(MockLocalS3Client()))

    def test_copy_single_object(self):
        exp = self._explorer()
        # Copy a single object
        exp.copy("dev-data", "config/settings.json", "dev-data", "backup/settings.json")
        # Verify the copy exists
        data = exp.client.download_object("dev-data", "backup/settings.json")
        assert data == b'{"env":"local","debug":true}'

    def test_copy_prefix(self):
        exp = self._explorer()
        # Copy all objects under raw/ prefix
        copied = exp.copy_prefix("dev-data", "raw/", "dev-data", "backup/raw/")
        assert len(copied) == 3
        # Verify the copies exist
        for key in copied:
            data = exp.client.download_object("dev-data", f"backup/raw/{key}")
            assert len(data) > 0
