"""HAR 1.2 file parser for CSRF Shield AI.

Parses HTTP Archive (HAR) files into HttpExchange dataclass instances
for downstream static analysis and ML classification.

Supported content types:
    - application/x-www-form-urlencoded (FR-102)
    - multipart/form-data — text fields only (FR-103)
    - application/json (FR-104)

Supports postData.params fallback for truncated bodies (FR-107).

Ref:
    - HAR 1.2 Spec: http://www.softwareishard.com/blog/har-12-spec/
    - spec/Design.md §2.2 Phase Responsibilities
    - docs/proposal/PROPOSAL.md §7.2 (HAR Importer)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

from src.input.models import HttpExchange

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------


class HarParseError(Exception):
    """Raised when a HAR file is invalid or cannot be parsed."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_har_file(path: Union[str, Path]) -> List[HttpExchange]:
    """Parse a HAR 1.2 file and return a list of HttpExchange objects.

    Args:
        path: Path to the HAR file (JSON format).

    Returns:
        List of HttpExchange instances, one per HAR entry.

    Raises:
        HarParseError: If the file is not valid HAR 1.2.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"HAR file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise HarParseError(f"Invalid JSON in HAR file: {e}") from e

    _validate_har(data)

    entries = data["log"]["entries"]
    exchanges: List[HttpExchange] = []

    for i, entry in enumerate(entries):
        try:
            exchange = _parse_entry(entry)
            exchanges.append(exchange)
        except (KeyError, ValueError) as e:
            logger.warning("Skipping entry %d: %s", i, e)

    logger.info("Parsed %d exchanges from %s", len(exchanges), path.name)
    return exchanges


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_har(data: dict) -> None:
    """Validate that the data conforms to HAR 1.2 structure.

    Checks for required top-level keys: log, log.version, log.entries.

    Args:
        data: Parsed JSON data from the HAR file.

    Raises:
        HarParseError: If required keys are missing or version is unsupported.
    """
    if not isinstance(data, dict):
        raise HarParseError("HAR data must be a JSON object")

    if "log" not in data:
        raise HarParseError("Missing required 'log' key in HAR data")

    log = data["log"]
    if not isinstance(log, dict):
        raise HarParseError("'log' must be a JSON object")

    if "entries" not in log:
        raise HarParseError("Missing required 'entries' key in HAR log")

    if not isinstance(log["entries"], list):
        raise HarParseError("'entries' must be a JSON array")

    version = log.get("version", "")
    if version and not version.startswith("1."):
        logger.warning("HAR version %s may not be fully supported (expected 1.x)", version)


# ---------------------------------------------------------------------------
# Entry Parsing
# ---------------------------------------------------------------------------


def _parse_entry(entry: dict) -> HttpExchange:
    """Parse a single HAR entry into an HttpExchange.

    Args:
        entry: A single item from har.log.entries[].

    Returns:
        HttpExchange instance populated from the entry data.

    Raises:
        KeyError: If required fields are missing from the entry.
    """
    request = entry["request"]
    response = entry["response"]

    # Extract headers and cookies
    request_headers = _extract_headers(request.get("headers", []))
    request_cookies = _extract_cookies(request.get("cookies", []))
    response_headers = _extract_headers(response.get("headers", []))

    # Extract body via postData (handles all content types + fallback)
    post_data = request.get("postData")
    request_body = _parse_body(post_data)
    request_content_type = ""
    if post_data:
        request_content_type = post_data.get("mimeType", "")
    elif "Content-Type" in request_headers:
        request_content_type = request_headers["Content-Type"]

    # Extract response body
    response_content = response.get("content", {})
    response_body = response_content.get("text")

    # Parse timestamp
    timestamp = _parse_timestamp(entry.get("startedDateTime", ""))

    return HttpExchange(
        request_method=request["method"].upper(),
        request_url=request["url"],
        request_headers=request_headers,
        request_cookies=request_cookies,
        request_body=request_body,
        request_content_type=request_content_type,
        response_status=response["status"],
        response_headers=response_headers,
        response_body=response_body,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Header / Cookie Extraction
# ---------------------------------------------------------------------------


def _extract_headers(headers_list: list) -> Dict[str, str]:
    """Convert HAR headers array to a flat dict.

    HAR stores headers as ``[{"name": "Host", "value": "example.com"}, ...]``.
    Duplicate header names are joined with ``, `` (RFC 7230 §3.2.2).

    Args:
        headers_list: List of name/value dicts from HAR.

    Returns:
        Dict mapping header names to values.
    """
    result: Dict[str, str] = {}
    for item in headers_list:
        name = item.get("name", "")
        value = item.get("value", "")
        if name in result:
            result[name] = f"{result[name]}, {value}"
        else:
            result[name] = value
    return result


def _extract_cookies(cookies_list: list) -> Dict[str, str]:
    """Convert HAR cookies array to a flat dict.

    HAR stores cookies as ``[{"name": "sid", "value": "abc123"}, ...]``.

    Args:
        cookies_list: List of name/value dicts from HAR.

    Returns:
        Dict mapping cookie names to values.
    """
    return {
        item.get("name", ""): item.get("value", "")
        for item in cookies_list
        if item.get("name")
    }


# ---------------------------------------------------------------------------
# Body Parsing (T-123, T-124, T-125, T-126)
# ---------------------------------------------------------------------------


def _parse_body(post_data: Optional[dict]) -> Optional[str]:
    """Parse the request body from HAR postData.

    Routing logic:
        1. If postData is None → return None (GET requests, etc.)
        2. If postData.text exists → return it directly
        3. If postData.text is missing but postData.params exists →
           reconstruct body from params (FR-107 truncated body fallback)

    Args:
        post_data: The postData object from a HAR request entry.

    Returns:
        The request body as a string, or None if absent.
    """
    if post_data is None:
        return None

    # Primary: use .text field directly (handles all content types)
    text = post_data.get("text")
    if text is not None:
        return text

    # Fallback: reconstruct from .params (FR-107)
    params = post_data.get("params")
    if params:
        return _params_fallback(params)

    return None


def _params_fallback(params: list) -> str:
    """Reconstruct a URL-encoded body from postData.params.

    This handles the case where browsers truncate the raw body text but
    still provide the parsed parameter list. We reconstruct as
    application/x-www-form-urlencoded.

    Args:
        params: List of ``{"name": ..., "value": ...}`` dicts from HAR.

    Returns:
        URL-encoded string of the parameters.
    """
    pairs = [
        (item.get("name", ""), item.get("value", ""))
        for item in params
        if item.get("name") is not None
    ]
    return urlencode(pairs)


# ---------------------------------------------------------------------------
# Timestamp Parsing
# ---------------------------------------------------------------------------


def _parse_timestamp(iso_str: str) -> datetime:
    """Parse an ISO 8601 timestamp from HAR's startedDateTime.

    HAR uses ISO 8601 format: ``2026-02-24T12:00:00.000+07:00``.
    Falls back to ``datetime.now()`` if parsing fails.

    Args:
        iso_str: ISO 8601 timestamp string.

    Returns:
        Parsed datetime object.
    """
    if not iso_str:
        return datetime.now()

    try:
        # Python 3.11+ handles most ISO 8601 formats
        return datetime.fromisoformat(iso_str)
    except ValueError:
        # Strip trailing Z (UTC indicator not handled by fromisoformat < 3.11)
        try:
            cleaned = iso_str.replace("Z", "+00:00")
            return datetime.fromisoformat(cleaned)
        except ValueError:
            logger.warning("Could not parse timestamp '%s', using now()", iso_str)
            return datetime.now()
