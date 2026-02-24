"""Unit tests for the flow reconstructor.

Tests session identification, exchange grouping, chronological sorting,
and edge cases.

Ref:
    - spec/Tasks.md T-134
    - .agent/instructions/testing_strategy.instructions.md §2.1
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src.input.flow_reconstructor import (
    DEFAULT_SESSION_COOKIE_PATTERNS,
    _identify_session,
    reconstruct_flows,
)
from src.input.models import AuthMechanism, HttpExchange


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exchange(
    method: str = "GET",
    url: str = "https://example.com/",
    cookies: dict | None = None,
    timestamp: datetime | None = None,
) -> HttpExchange:
    """Helper to create an HttpExchange with minimal boilerplate."""
    return HttpExchange(
        request_method=method,
        request_url=url,
        request_headers={},
        request_cookies=cookies or {},
        request_body=None,
        request_content_type="",
        response_status=200,
        response_headers={},
        response_body=None,
        timestamp=timestamp or datetime(2026, 1, 1),
    )


# ---------------------------------------------------------------------------
# Session Identification (T-131)
# ---------------------------------------------------------------------------


class TestIdentifySession:
    """Tests for _identify_session()."""

    def test_matches_session_id_cookie(self) -> None:
        """Cookie named 'session_id' matches default pattern 'session'."""
        ex = _make_exchange(cookies={"session_id": "abc123"})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result == "abc123"

    def test_matches_sid_cookie(self) -> None:
        """Cookie named 'sid' matches default pattern 'sid'."""
        ex = _make_exchange(cookies={"sid": "sess_xyz"})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result == "sess_xyz"

    def test_matches_jsessionid(self) -> None:
        """Cookie 'JSESSIONID' contains 'session' (case-insensitive)."""
        ex = _make_exchange(cookies={"JSESSIONID": "jvm_abc"})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result == "jvm_abc"

    def test_matches_auth_token_cookie(self) -> None:
        """Cookie 'auth_token' matches default pattern 'auth'."""
        ex = _make_exchange(cookies={"auth_token": "tok_456"})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result == "tok_456"

    def test_case_insensitive(self) -> None:
        """Pattern matching is case-insensitive."""
        ex = _make_exchange(cookies={"SESSION_ID": "upper_case"})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result == "upper_case"

    def test_no_match_generates_fallback(self) -> None:
        """No matching cookie generates a 'no-session-' prefixed ID."""
        ex = _make_exchange(cookies={"tracking_id": "track123"})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result.startswith("no-session-")

    def test_no_cookies_generates_fallback(self) -> None:
        """Exchange with no cookies generates a fallback ID."""
        ex = _make_exchange(cookies={})
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result.startswith("no-session-")

    def test_custom_pattern(self) -> None:
        """Custom cookie patterns are used when provided."""
        ex = _make_exchange(cookies={"my_token": "custom123"})
        result = _identify_session(ex, ["token"])
        assert result == "custom123"

    def test_first_match_wins(self) -> None:
        """When multiple cookies match, the first one wins."""
        ex = _make_exchange(
            cookies={"session_id": "sess_1", "sid": "sess_2"}
        )
        result = _identify_session(ex, DEFAULT_SESSION_COOKIE_PATTERNS)
        assert result == "sess_1"


# ---------------------------------------------------------------------------
# Exchange Grouping (T-132)
# ---------------------------------------------------------------------------


class TestReconstructFlows:
    """Tests for reconstruct_flows()."""

    def test_single_session(self) -> None:
        """Exchanges with the same session cookie form one flow."""
        exchanges = [
            _make_exchange(cookies={"session_id": "s1"}, timestamp=datetime(2026, 1, 1, 12, 0)),
            _make_exchange(cookies={"session_id": "s1"}, timestamp=datetime(2026, 1, 1, 12, 1)),
        ]
        flows = reconstruct_flows(exchanges)
        assert len(flows) == 1
        assert flows[0].session_id == "s1"
        assert len(flows[0].exchanges) == 2

    def test_multiple_sessions(self) -> None:
        """Different session cookies produce separate flows."""
        exchanges = [
            _make_exchange(cookies={"session_id": "s1"}, timestamp=datetime(2026, 1, 1, 12, 0)),
            _make_exchange(cookies={"session_id": "s2"}, timestamp=datetime(2026, 1, 1, 12, 1)),
            _make_exchange(cookies={"session_id": "s1"}, timestamp=datetime(2026, 1, 1, 12, 2)),
        ]
        flows = reconstruct_flows(exchanges)
        assert len(flows) == 2

        s1_flow = next(f for f in flows if f.session_id == "s1")
        s2_flow = next(f for f in flows if f.session_id == "s2")
        assert len(s1_flow.exchanges) == 2
        assert len(s2_flow.exchanges) == 1

    def test_empty_exchanges(self) -> None:
        """Empty exchange list returns empty flows list."""
        flows = reconstruct_flows([])
        assert flows == []

    def test_auth_mechanism_defaults_to_none(self) -> None:
        """Auth mechanism is set to NONE (real detection in T-141)."""
        exchanges = [_make_exchange(cookies={"session_id": "s1"})]
        flows = reconstruct_flows(exchanges)
        assert flows[0].auth_mechanism == AuthMechanism.NONE

    def test_no_cookie_exchanges_separate(self) -> None:
        """Exchanges without session cookies get unique fallback IDs."""
        exchanges = [
            _make_exchange(cookies={}, timestamp=datetime(2026, 1, 1, 12, 0)),
            _make_exchange(cookies={}, timestamp=datetime(2026, 1, 1, 12, 1)),
        ]
        flows = reconstruct_flows(exchanges)
        # Each gets a unique fallback → separate flows
        assert len(flows) == 2
        assert all(f.session_id.startswith("no-session-") for f in flows)

    def test_mixed_cookie_and_no_cookie(self) -> None:
        """Mix of session-cookied and cookieless exchanges."""
        exchanges = [
            _make_exchange(cookies={"session_id": "s1"}, timestamp=datetime(2026, 1, 1, 12, 0)),
            _make_exchange(cookies={}, timestamp=datetime(2026, 1, 1, 12, 1)),
            _make_exchange(cookies={"session_id": "s1"}, timestamp=datetime(2026, 1, 1, 12, 2)),
        ]
        flows = reconstruct_flows(exchanges)
        # 1 flow for s1 + 1 flow for the no-cookie exchange
        assert len(flows) == 2

        s1_flow = next(f for f in flows if f.session_id == "s1")
        assert len(s1_flow.exchanges) == 2

    def test_custom_cookie_patterns(self) -> None:
        """Custom cookie patterns can be passed to reconstruct_flows."""
        exchanges = [
            _make_exchange(cookies={"my_token": "tok_1"}, timestamp=datetime(2026, 1, 1)),
        ]
        flows = reconstruct_flows(exchanges, cookie_patterns=["token"])
        assert len(flows) == 1
        assert flows[0].session_id == "tok_1"


# ---------------------------------------------------------------------------
# Chronological Sorting (T-133)
# ---------------------------------------------------------------------------


class TestChronologicalSorting:
    """Tests for chronological ordering within flows."""

    def test_sorts_exchanges_by_timestamp(self) -> None:
        """Exchanges within a flow are sorted by timestamp."""
        exchanges = [
            _make_exchange(
                url="https://example.com/3",
                cookies={"session_id": "s1"},
                timestamp=datetime(2026, 1, 1, 12, 30),
            ),
            _make_exchange(
                url="https://example.com/1",
                cookies={"session_id": "s1"},
                timestamp=datetime(2026, 1, 1, 12, 0),
            ),
            _make_exchange(
                url="https://example.com/2",
                cookies={"session_id": "s1"},
                timestamp=datetime(2026, 1, 1, 12, 15),
            ),
        ]
        flows = reconstruct_flows(exchanges)
        assert len(flows) == 1

        urls = [e.request_url for e in flows[0].exchanges]
        assert urls == [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]

    def test_flows_sorted_by_first_exchange(self) -> None:
        """Multiple flows are sorted by their first exchange timestamp."""
        exchanges = [
            _make_exchange(cookies={"session_id": "late"}, timestamp=datetime(2026, 1, 2)),
            _make_exchange(cookies={"session_id": "early"}, timestamp=datetime(2026, 1, 1)),
        ]
        flows = reconstruct_flows(exchanges)
        assert flows[0].session_id == "early"
        assert flows[1].session_id == "late"
