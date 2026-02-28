"""Remediation recommendations for CSRF findings.

Maps each CSRF rule ID to a specific, actionable fix recommendation.

Ref:
    - spec/Tasks.md T-414
    - spec/Requirements.md FR-503
"""

from __future__ import annotations

from typing import Dict

# Rule ID → (short title, detailed recommendation).
REMEDIATIONS: Dict[str, tuple[str, str]] = {
    "CSRF-001": (
        "Add CSRF Token to Forms",
        "Include a hidden CSRF token in every HTML form that performs "
        "state-changing operations. Use your framework's built-in CSRF "
        "protection (e.g., Django {% csrf_token %}, Rails "
        "authenticity_token). Ensure the token is validated server-side "
        "on every POST request.",
    ),
    "CSRF-002": (
        "Add CSRF Token Header",
        "For AJAX/API requests, include a CSRF token in a custom "
        "header (e.g., X-CSRF-Token). Configure your framework to "
        "validate this header on state-changing requests. Use a "
        "meta tag or cookie to transmit the token to JavaScript.",
    ),
    "CSRF-003": (
        "Use Unpredictable Token Values",
        "CSRF tokens must be cryptographically random and unique per "
        "session or per request. Use secrets.token_hex(32) or your "
        "framework's secure token generator. Never use sequential IDs "
        "or timestamps as CSRF tokens.",
    ),
    "CSRF-004": (
        "Rotate CSRF Tokens",
        "CSRF tokens should not remain static across requests. "
        "Implement per-request or per-session token rotation. "
        "Regenerate the token after each state-changing request to "
        "prevent token replay attacks.",
    ),
    "CSRF-005": (
        "Set SameSite Cookie Attribute",
        "Set the SameSite attribute to 'Strict' or 'Lax' on all "
        "session cookies. SameSite=Strict prevents cross-site request "
        "submission entirely. SameSite=Lax allows safe top-level "
        "navigations but blocks cross-origin POST requests.",
    ),
    "CSRF-006": (
        "Require Authentication for State Changes",
        "Ensure all state-changing endpoints require authentication. "
        "Unauthenticated endpoints that modify data are vulnerable to "
        "CSRF by definition. Apply authentication middleware to all "
        "routes that accept POST, PUT, PATCH, or DELETE.",
    ),
    "CSRF-007": (
        "Validate Origin Header",
        "Check the Origin header on incoming requests and reject any "
        "request whose origin does not match your application's domain. "
        "This provides defense-in-depth alongside CSRF tokens. "
        "Fall back to Referer validation if Origin is absent.",
    ),
    "CSRF-008": (
        "Avoid State Changes via GET",
        "Never perform state-changing operations (create, update, "
        "delete) via GET requests. GET requests are trivially "
        "forgeable via <img> tags, links, and redirects. Use POST, "
        "PUT, PATCH, or DELETE for all mutations.",
    ),
    "CSRF-009": (
        "Validate Referer Header",
        "As a secondary defense, validate the Referer header to ensure "
        "requests originate from your domain. Be aware that Referer "
        "can be suppressed (Referrer-Policy: no-referrer), so this "
        "should complement, not replace, token-based validation.",
    ),
    "CSRF-010": (
        "Use Proper Content-Type Validation",
        "Validate the Content-Type header on incoming requests. Reject "
        "requests with unexpected Content-Types (e.g., text/plain "
        "on an API that expects application/json). This prevents "
        "simple cross-origin form submissions to JSON APIs.",
    ),
    "CSRF-011": (
        "Header-Only Auth — Low CSRF Risk",
        "This endpoint uses header-only authentication (e.g., "
        "Bearer JWT, API key). These are inherently resistant to CSRF "
        "because browsers do not automatically attach custom headers "
        "to cross-origin requests. No immediate action required, but "
        "continue to avoid cookie-based auth for APIs.",
    ),
}


def get_remediation(rule_id: str) -> tuple[str, str]:
    """Get the remediation recommendation for a rule.

    Args:
        rule_id: The CSRF rule identifier (e.g., "CSRF-001").

    Returns:
        Tuple of (short_title, detailed_recommendation).
        Returns a generic recommendation if rule_id is unknown.
    """
    return REMEDIATIONS.get(
        rule_id,
        (
            "Review Finding",
            "Review this finding manually and apply appropriate "
            "CSRF protections based on the endpoint's requirements.",
        ),
    )
