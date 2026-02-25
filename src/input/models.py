"""Core data models for CSRF Shield AI.

Defines the 4 primary dataclasses and 3 supporting Enums used throughout
the analysis pipeline.

Ref:
    - spec/Design.md §3.1 (Core Entities)
    - docs/proposal/PROPOSAL.md §8.1 (Data Model)
    - .agent/instructions/coding_standards.instructions.md §2.4 (Data Models)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums — Fixed categories per coding_standards §2.4
# Using str mixin so values serialize naturally to JSON and compare with YAML.
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Severity level for a security finding.

    Maps to the severity column in config/rules.yaml and the
    severity_map in config/settings.yaml for score normalization.
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RiskLevel(str, Enum):
    """Overall risk classification for an analysis result.

    Thresholds defined in config/settings.yaml:
        0–20  = LOW
        21–40 = MEDIUM
        41–70 = HIGH
        71–100 = CRITICAL
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AuthMechanism(str, Enum):
    """Authentication mechanism detected in a session flow.

    Ref: coding_standards.instructions.md §1.3
        - COOKIE:      Session relies on cookies (CSRF-relevant)
        - HEADER_ONLY: Bearer / API-key only (triggers short-circuit)
        - MIXED:       Both cookies and auth headers present
        - NONE:        No authentication detected
    """

    COOKIE = "cookie"
    HEADER_ONLY = "header_only"
    MIXED = "mixed"
    NONE = "none"


# ---------------------------------------------------------------------------
# Dataclasses — All frozen=True per coding_standards §2.4
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HttpExchange:
    """A single HTTP request/response pair extracted from a HAR file.

    Represents one complete round-trip captured by the browser or proxy.
    Immutable after construction — analysis never mutates traffic data.

    Attributes:
        request_method: HTTP method (GET, POST, PUT, DELETE, PATCH).
        request_url: Full request URL including query string.
        request_headers: Request headers as key-value pairs.
        request_cookies: Parsed cookies from the Cookie header.
        request_body: Raw request body (None for GET requests or empty bodies).
        request_content_type: Value of the Content-Type request header.
        response_status: HTTP response status code.
        response_headers: Response headers as key-value pairs.
        response_body: Raw response body (None if not captured).
        timestamp: When the exchange occurred.

    Ref: FR-101, spec/Design.md §3.1
    """

    request_method: str
    request_url: str
    request_headers: Dict[str, str]
    request_cookies: Dict[str, str]
    request_body: Optional[str]
    request_content_type: str
    response_status: int
    response_headers: Dict[str, str]
    response_body: Optional[str]
    timestamp: datetime


@dataclass(frozen=True)
class SessionFlow:
    """An ordered sequence of exchanges belonging to one user session.

    Groups related HTTP exchanges by session ID (typically derived from
    a session cookie). The auth_mechanism field drives the short-circuit
    decision in the analysis pipeline.

    Attributes:
        session_id: Derived from session cookie value or auto-generated UUID.
        exchanges: Chronologically ordered list of HttpExchange objects.
        auth_mechanism: Detected authentication type for this session.

    Ref: FR-105, spec/Design.md §3.1
    """

    session_id: str
    exchanges: List[HttpExchange]
    auth_mechanism: AuthMechanism


@dataclass(frozen=True)
class Finding:
    """A single security finding produced by a static analysis rule.

    Each rule (CSRF-001 through CSRF-011) can produce zero or more
    Finding objects per exchange analyzed.

    Attributes:
        rule_id: Rule identifier (e.g., 'CSRF-001').
        rule_name: Human-readable rule name.
        severity: Severity level from the rule definition.
        description: What was found — specific to this instance.
        evidence: Supporting data (e.g., header value, token snippet).
        exchange: The HttpExchange that triggered this finding.

    Ref: FR-201, spec/Design.md §3.1
    """

    rule_id: str
    rule_name: str
    severity: Severity
    description: str
    evidence: str
    exchange: HttpExchange


@dataclass(frozen=True)
class AnalysisResult:
    """Final analysis output for a single endpoint/flow.

    Produced by the pipeline for each analyzed session flow. When the
    auth detector triggers a short-circuit (header_only auth), the
    ``ml_probability`` and ``feature_vector`` fields are None because
    the ML pipeline is completely skipped. The risk scorer is also
    bypassed — the fixed score of 5 (LOW) is assigned directly.

    Attributes:
        endpoint: URL path of the analyzed endpoint.
        http_method: HTTP method of the primary request.
        risk_score: Quantified risk score (0–100).
        risk_level: Classified risk level.
        findings: All findings from static analysis rules.
        ml_probability: ML model prediction (None if short-circuited).
        feature_vector: Extracted features (None if short-circuited).
        recommendations: Remediation suggestions.

    Ref: FR-401, FR-404, spec/Design.md §3.1
    """

    endpoint: str
    http_method: str
    risk_score: int
    risk_level: RiskLevel
    findings: List[Finding]
    recommendations: List[str]
    ml_probability: Optional[float] = None
    feature_vector: Optional[Dict[str, Any]] = None
