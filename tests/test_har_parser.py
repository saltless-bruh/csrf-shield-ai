"""Unit tests for HAR 1.2 parser.

Tests parse_har_file() and all internal helpers against the sample
HAR fixtures in data/sample_har/.

Ref:
    - spec/Tasks.md T-127
    - .agent/instructions/testing_strategy.instructions.md §2.1
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.input.har_parser import HarParseError, parse_har_file
from src.input.models import HttpExchange

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_har"


# ---------------------------------------------------------------------------
# HAR File Parsing — Valid Files (T-121, T-122)
# ---------------------------------------------------------------------------


class TestParseHarFileValid:
    """Tests for parse_har_file() with valid HAR files."""

    def test_minimal_har(self) -> None:
        """Parse minimal.har — single GET request."""
        exchanges = parse_har_file(SAMPLE_DIR / "minimal.har")
        assert len(exchanges) == 1

        ex = exchanges[0]
        assert isinstance(ex, HttpExchange)
        assert ex.request_method == "GET"
        assert ex.request_url == "https://example.com/"
        assert ex.response_status == 200

    def test_minimal_har_headers(self) -> None:
        """Headers are extracted as a flat dict."""
        exchanges = parse_har_file(SAMPLE_DIR / "minimal.har")
        ex = exchanges[0]
        assert ex.request_headers["Host"] == "example.com"
        assert ex.request_headers["Accept"] == "text/html"

    def test_minimal_har_response_body(self) -> None:
        """Response body is extracted from content.text."""
        exchanges = parse_har_file(SAMPLE_DIR / "minimal.har")
        ex = exchanges[0]
        assert ex.response_body == "<html><body>Welcome</body></html>"

    def test_minimal_har_no_body(self) -> None:
        """GET request has no request body."""
        exchanges = parse_har_file(SAMPLE_DIR / "minimal.har")
        ex = exchanges[0]
        assert ex.request_body is None

    def test_minimal_har_timestamp(self) -> None:
        """Timestamp is parsed from startedDateTime."""
        exchanges = parse_har_file(SAMPLE_DIR / "minimal.har")
        ex = exchanges[0]
        assert ex.timestamp.year == 2026
        assert ex.timestamp.month == 2
        assert ex.timestamp.day == 24

    def test_response_cookies_in_headers(self) -> None:
        """Response Set-Cookie appears in response_headers."""
        exchanges = parse_har_file(SAMPLE_DIR / "minimal.har")
        ex = exchanges[0]
        assert "Set-Cookie" in ex.response_headers


# ---------------------------------------------------------------------------
# Form URL-Encoded Body (T-123)
# ---------------------------------------------------------------------------


class TestFormUrlEncoded:
    """Tests for application/x-www-form-urlencoded body parsing."""

    def test_form_body_extracted(self) -> None:
        """Form body text is extracted from postData.text."""
        exchanges = parse_har_file(SAMPLE_DIR / "form_urlencoded.har")
        ex = exchanges[0]
        assert ex.request_body is not None
        assert "csrf_token=a1b2c3d4e5f6g7h8i9j0" in ex.request_body

    def test_form_content_type(self) -> None:
        """Content type is set to urlencoded."""
        exchanges = parse_har_file(SAMPLE_DIR / "form_urlencoded.har")
        ex = exchanges[0]
        assert "x-www-form-urlencoded" in ex.request_content_type

    def test_form_method_is_post(self) -> None:
        """Request method is POST."""
        exchanges = parse_har_file(SAMPLE_DIR / "form_urlencoded.har")
        ex = exchanges[0]
        assert ex.request_method == "POST"

    def test_form_cookies(self) -> None:
        """Session cookie is extracted."""
        exchanges = parse_har_file(SAMPLE_DIR / "form_urlencoded.har")
        ex = exchanges[0]
        assert ex.request_cookies.get("session_id") == "abc123"


# ---------------------------------------------------------------------------
# Multipart Form Data (T-124)
# ---------------------------------------------------------------------------


class TestMultipartForm:
    """Tests for multipart/form-data body parsing (text fields only)."""

    def test_multipart_body_extracted(self) -> None:
        """Multipart body text is returned as raw string."""
        exchanges = parse_har_file(SAMPLE_DIR / "multipart_form.har")
        ex = exchanges[0]
        assert ex.request_body is not None
        assert "csrf_token" in ex.request_body
        assert "My Document" in ex.request_body

    def test_multipart_content_type(self) -> None:
        """Content type includes multipart/form-data."""
        exchanges = parse_har_file(SAMPLE_DIR / "multipart_form.har")
        ex = exchanges[0]
        assert "multipart/form-data" in ex.request_content_type

    def test_multipart_response_status(self) -> None:
        """Response status is 201 Created."""
        exchanges = parse_har_file(SAMPLE_DIR / "multipart_form.har")
        ex = exchanges[0]
        assert ex.response_status == 201


# ---------------------------------------------------------------------------
# JSON Body (T-125)
# ---------------------------------------------------------------------------


class TestJsonBody:
    """Tests for application/json body parsing."""

    def test_json_body_extracted(self) -> None:
        """JSON body text is returned as raw string."""
        exchanges = parse_har_file(SAMPLE_DIR / "json_body.har")
        ex = exchanges[0]
        assert ex.request_body is not None
        # Verify it's valid JSON and contains expected fields
        body = json.loads(ex.request_body)
        assert body["name"] == "Jane Doe"
        assert body["role"] == "admin"

    def test_json_content_type(self) -> None:
        """Content type is application/json."""
        exchanges = parse_har_file(SAMPLE_DIR / "json_body.har")
        ex = exchanges[0]
        assert "application/json" in ex.request_content_type

    def test_json_response_body(self) -> None:
        """Response body contains JSON data."""
        exchanges = parse_har_file(SAMPLE_DIR / "json_body.har")
        ex = exchanges[0]
        assert ex.response_body is not None
        resp = json.loads(ex.response_body)
        assert resp["id"] == 42


# ---------------------------------------------------------------------------
# Truncated Body / params Fallback (T-126)
# ---------------------------------------------------------------------------


class TestTruncatedBody:
    """Tests for postData.params fallback when .text is missing (FR-107)."""

    def test_params_fallback_reconstructs_body(self) -> None:
        """When postData.text is missing, body is rebuilt from .params."""
        exchanges = parse_har_file(SAMPLE_DIR / "truncated_body.har")
        ex = exchanges[0]
        assert ex.request_body is not None
        # Params fallback produces URL-encoded body
        assert "theme=dark" in ex.request_body
        assert "language=en" in ex.request_body
        assert "csrf_token=truncated_tok_abc123" in ex.request_body

    def test_params_fallback_content_type(self) -> None:
        """Content type is preserved from postData.mimeType."""
        exchanges = parse_har_file(SAMPLE_DIR / "truncated_body.har")
        ex = exchanges[0]
        assert "x-www-form-urlencoded" in ex.request_content_type


# ---------------------------------------------------------------------------
# Bearer Auth HAR (for downstream short-circuit tests)
# ---------------------------------------------------------------------------


class TestBearerAuthHar:
    """Tests for bearer_auth.har fixture parsing."""

    def test_bearer_auth_headers(self) -> None:
        """Authorization header is extracted."""
        exchanges = parse_har_file(SAMPLE_DIR / "bearer_auth.har")
        ex = exchanges[0]
        assert "Authorization" in ex.request_headers
        assert ex.request_headers["Authorization"].startswith("Bearer ")

    def test_bearer_auth_no_cookies(self) -> None:
        """No cookies in a Bearer-only request."""
        exchanges = parse_har_file(SAMPLE_DIR / "bearer_auth.har")
        ex = exchanges[0]
        assert ex.request_cookies == {}

    def test_bearer_auth_no_body(self) -> None:
        """GET request has no body."""
        exchanges = parse_har_file(SAMPLE_DIR / "bearer_auth.har")
        ex = exchanges[0]
        assert ex.request_body is None


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestHarParseErrors:
    """Tests for invalid HAR files and error conditions."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError raised for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_har_file(tmp_path / "nonexistent.har")

    def test_invalid_json(self, tmp_path: Path) -> None:
        """HarParseError raised for invalid JSON."""
        bad_file = tmp_path / "bad.har"
        bad_file.write_text("not json {{{")
        with pytest.raises(HarParseError, match="Invalid JSON"):
            parse_har_file(bad_file)

    def test_missing_log_key(self, tmp_path: Path) -> None:
        """HarParseError raised when 'log' key is missing."""
        bad_file = tmp_path / "no_log.har"
        bad_file.write_text(json.dumps({"version": "1.2"}))
        with pytest.raises(HarParseError, match="Missing required 'log'"):
            parse_har_file(bad_file)

    def test_missing_entries_key(self, tmp_path: Path) -> None:
        """HarParseError raised when 'entries' key is missing."""
        bad_file = tmp_path / "no_entries.har"
        bad_file.write_text(json.dumps({"log": {"version": "1.2"}}))
        with pytest.raises(HarParseError, match="Missing required 'entries'"):
            parse_har_file(bad_file)

    def test_empty_entries(self, tmp_path: Path) -> None:
        """Empty entries list returns empty exchanges list."""
        har_file = tmp_path / "empty.har"
        har_file.write_text(
            json.dumps({"log": {"version": "1.2", "entries": []}})
        )
        exchanges = parse_har_file(har_file)
        assert exchanges == []

    def test_malformed_entry_is_skipped(self, tmp_path: Path) -> None:
        """Malformed entries are skipped, valid ones are kept."""
        har_data = {
            "log": {
                "version": "1.2",
                "entries": [
                    {},  # missing request/response — will be skipped
                    {
                        "startedDateTime": "2026-01-01T00:00:00.000Z",
                        "request": {
                            "method": "GET",
                            "url": "https://example.com/",
                            "headers": [],
                            "cookies": [],
                        },
                        "response": {
                            "status": 200,
                            "headers": [],
                            "content": {},
                        },
                    },
                ],
            }
        }
        har_file = tmp_path / "mixed.har"
        har_file.write_text(json.dumps(har_data))
        exchanges = parse_har_file(har_file)
        assert len(exchanges) == 1
        assert exchanges[0].request_method == "GET"
