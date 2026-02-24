"""Flow reconstructor for CSRF Shield AI.

Groups parsed HttpExchange objects into SessionFlow objects by session cookie.
Exchanges within each flow are sorted chronologically.

Ref:
    - spec/Design.md §2.2 Phase 1 Responsibilities
    - spec/Requirements.md FR-105
    - config/settings.yaml — session_cookie_patterns
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Dict, List, Optional

from src.input.models import AuthMechanism, HttpExchange, SessionFlow

logger = logging.getLogger(__name__)

# Default patterns — matches settings.yaml auth_detection.session_cookie_patterns
DEFAULT_SESSION_COOKIE_PATTERNS: List[str] = ["session", "sid", "auth"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def reconstruct_flows(
    exchanges: List[HttpExchange],
    cookie_patterns: Optional[List[str]] = None,
) -> List[SessionFlow]:
    """Group exchanges into SessionFlow objects by session cookie.

    Identifies session cookies by matching cookie names against known
    patterns (case-insensitive substring match). Exchanges with the
    same session cookie value are grouped together and sorted
    chronologically.

    Auth mechanism is set to ``AuthMechanism.NONE`` — real detection
    is deferred to Milestone 5 (T-141).

    Args:
        exchanges: Flat list of HttpExchange objects (e.g., from
            ``parse_har_file()``).
        cookie_patterns: Optional list of substrings to match against
            cookie names. Defaults to ``["session", "sid", "auth"]``.

    Returns:
        List of SessionFlow objects, one per unique session ID.
        Flows are sorted by the timestamp of their first exchange.
    """
    if not exchanges:
        return []

    patterns = cookie_patterns or DEFAULT_SESSION_COOKIE_PATTERNS

    # Group exchanges by session ID
    groups: Dict[str, List[HttpExchange]] = defaultdict(list)
    for exchange in exchanges:
        session_id = _identify_session(exchange, patterns)
        groups[session_id].append(exchange)

    # Build SessionFlow objects, sorting exchanges chronologically
    flows: List[SessionFlow] = []
    for session_id, group in groups.items():
        sorted_exchanges = sorted(group, key=lambda e: e.timestamp)
        flow = SessionFlow(
            session_id=session_id,
            exchanges=sorted_exchanges,
            auth_mechanism=AuthMechanism.NONE,  # Set by auth detector later
        )
        flows.append(flow)

    # Sort flows by first exchange timestamp for deterministic ordering
    flows.sort(key=lambda f: f.exchanges[0].timestamp)

    logger.info(
        "Reconstructed %d session flow(s) from %d exchange(s)",
        len(flows),
        len(exchanges),
    )
    return flows


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _identify_session(
    exchange: HttpExchange,
    patterns: List[str],
) -> str:
    """Identify the session ID from an exchange's cookies.

    Scans ``exchange.request_cookies`` for any cookie name that contains
    one of the given patterns (case-insensitive substring match). Returns
    the value of the first matching cookie.

    If no session cookie is found, generates a unique fallback ID with a
    ``"no-session-"`` prefix.

    Args:
        exchange: The HTTP exchange to inspect.
        patterns: List of substrings to match against cookie names.

    Returns:
        The session ID string.
    """
    for cookie_name, cookie_value in exchange.request_cookies.items():
        cookie_name_lower = cookie_name.lower()
        for pattern in patterns:
            if pattern.lower() in cookie_name_lower:
                return cookie_value

    # No session cookie found — generate fallback
    return f"no-session-{uuid.uuid4().hex[:8]}"
