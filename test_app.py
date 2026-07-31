import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("DDNS_PROXY_TOKEN", "test-token")
os.environ.setdefault("ALIYUN_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("ALIYUN_ACCESS_KEY_SECRET", "test-secret")

import app  # noqa: E402


class FakeClient:
    def __init__(self, records):
        self.records = records
        self.describe_request = None
        self.updated_request = None
        self.added_request = None

    def describe_sub_domain_records(self, request):
        self.describe_request = request
        return SimpleNamespace(
            body=SimpleNamespace(
                domain_records=SimpleNamespace(record=self.records),
            ),
        )

    def update_domain_record(self, request):
        self.updated_request = request

    def add_domain_record(self, request):
        self.added_request = request


class UpdateRecordTest(unittest.TestCase):
    def test_describes_exact_subdomain(self):
        client = FakeClient([])

        with patch.object(app, "get_client", return_value=client):
            app.update_record("proxy.example.com", "1.2.3.4")

        self.assertEqual(client.describe_request.domain_name, "example.com")
        self.assertEqual(client.describe_request.sub_domain, "proxy.example.com")
        self.assertEqual(client.describe_request.type, "A")

    def test_skips_update_when_record_value_is_unchanged(self):
        client = FakeClient([SimpleNamespace(record_id="1", value="1.2.3.4")])

        with patch.object(app, "get_client", return_value=client):
            result = app.update_record("proxy.example.com", "1.2.3.4")

        self.assertEqual(result, "unchanged proxy.example.com -> 1.2.3.4")
        self.assertIsNone(client.updated_request)
        self.assertIsNone(client.added_request)

    def test_updates_existing_record_when_value_changed(self):
        client = FakeClient([SimpleNamespace(record_id="1", value="1.1.1.1")])

        with patch.object(app, "get_client", return_value=client):
            result = app.update_record("proxy.example.com", "1.2.3.4")

        self.assertEqual(result, "updated proxy.example.com -> 1.2.3.4")
        self.assertEqual(client.updated_request.record_id, "1")
        self.assertEqual(client.updated_request.rr, "proxy")
        self.assertEqual(client.updated_request.type, "A")
        self.assertEqual(client.updated_request.value, "1.2.3.4")

    def test_creates_record_when_missing(self):
        client = FakeClient([])

        with patch.object(app, "get_client", return_value=client):
            result = app.update_record("proxy.example.com", "1.2.3.4")

        self.assertEqual(result, "created proxy.example.com -> 1.2.3.4")
        self.assertEqual(client.added_request.domain_name, "example.com")
        self.assertEqual(client.added_request.rr, "proxy")
        self.assertEqual(client.added_request.type, "A")
        self.assertEqual(client.added_request.value, "1.2.3.4")


if __name__ == "__main__":
    unittest.main()
