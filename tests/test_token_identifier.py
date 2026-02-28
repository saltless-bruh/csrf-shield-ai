"""Unit tests for the CSRF token identification engine.

Tests cover all three identification tiers, header identification,
Shannon entropy calculation, and edge cases.

Ref:
    - src/analysis/token_identifier.py
    - docs/proposal/PROPOSAL.md §9.3.1
    - spec/Tasks.md T-204
    - .agent/instructions/testing_strategy.instructions.md §6
"""

from __future__ import annotations

import math


from src.analysis.token_identifier import (
    TokenMatch,
    identify_csrf_header,
    identify_csrf_token,
    parse_form_params,
    shannon_entropy,
)

# ===========================================================================
# T-202: Shannon Entropy Calculation
# ===========================================================================


class TestShannonEntropy:
    """Tests for the shannon_entropy() utility function."""

    def test_shannon_entropy_empty_string_returns_zero(self) -> None:
        """Empty string has no information — entropy is 0.0."""
        assert shannon_entropy("") == 0.0

    def test_shannon_entropy_single_char_repeated_returns_zero(self) -> None:
        """All identical characters have zero entropy."""
        assert shannon_entropy("aaaa") == 0.0
        assert shannon_entropy("zzzzzzzzzz") == 0.0

    def test_shannon_entropy_two_balanced_chars(self) -> None:
        """Perfectly balanced two-symbol string has entropy of 1.0 bit/char."""
        # "abab" → p(a)=0.5, p(b)=0.5 → H = -2 × 0.5×log₂(0.5) = 1.0
        result = shannon_entropy("abab")
        assert abs(result - 1.0) < 1e-9

    def test_shannon_entropy_all_unique_chars(self) -> None:
        """String with all unique chars has maximal entropy log₂(n)."""
        s = "abcd"  # 4 unique chars → max H = log₂(4) = 2.0
        result = shannon_entropy(s)
        assert abs(result - 2.0) < 1e-9

    def test_shannon_entropy_high_for_random_token(self) -> None:
        """A realistic random hex token should exceed the Tier 3 threshold."""
        token = "a3f8c2d1e9b4f7a0c6e3d2b1f0a4c8e5"  # 32-char hex
        result = shannon_entropy(token)
        assert result >= 3.5, f"Expected entropy ≥ 3.5, got {result:.3f}"

    def test_shannon_entropy_low_for_sequential_digits(self) -> None:
        """Sequential digits ('1234567890') have moderate entropy — verify."""
        result = shannon_entropy("1234567890")
        # 10 unique chars → log₂(10) ≈ 3.32 bits/char
        assert abs(result - math.log2(10)) < 1e-9

    def test_shannon_entropy_single_character_string(self) -> None:
        """Single character has zero entropy."""
        assert shannon_entropy("x") == 0.0

    def test_shannon_entropy_returns_float(self) -> None:
        """Return type is always float."""
        assert isinstance(shannon_entropy("hello"), float)


# ===========================================================================
# T-201 + T-203: Token Identification — Form Parameters
# ===========================================================================


class TestIdentifyCsrfTokenTier1:
    """Tier 1: Exact name match against CSRF_TOKEN_NAMES registry."""

    def test_identify_token_django_name(self) -> None:
        """csrfmiddlewaretoken (Django) → Tier 1 match."""
        params = {"name": "Alice", "csrfmiddlewaretoken": "abc123def456ghi789"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "csrfmiddlewaretoken"
        assert match.tier == 1
        assert match.source == "form"

    def test_identify_token_laravel_name(self) -> None:
        """_token (Laravel) → Tier 1 match."""
        params = {"email": "a@b.com", "_token": "randomtoken1234567890"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "_token"
        assert match.tier == 1

    def test_identify_token_rails_name(self) -> None:
        """authenticity_token (Rails) → Tier 1 match."""
        params = {"user[name]": "Bob", "authenticity_token": "railstokenvalue123456"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "authenticity_token"
        assert match.tier == 1

    def test_identify_token_aspnet_name(self) -> None:
        """__RequestVerificationToken (ASP.NET) → Tier 1 match."""
        params = {
            "Username": "admin",
            "__RequestVerificationToken": "CfDJ8Nrandom123456789",
        }
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "__RequestVerificationToken"
        assert match.tier == 1

    def test_identify_token_generic_csrf_token(self) -> None:
        """csrf_token (generic) → Tier 1 match."""
        params = {"data": "something", "csrf_token": "token_value_here_xyz"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "csrf_token"
        assert match.tier == 1

    def test_identify_token_case_insensitive_matching(self) -> None:
        """Tier 1 matching is case-insensitive (CSRF_TOKEN → match)."""
        params = {"CSRF_TOKEN": "SomeRandomHexValue123456789"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.tier == 1

    def test_identify_token_returns_correct_value(self) -> None:
        """Matched token value is preserved exactly."""
        token_value = "MyExact_TokenValue_12345"
        params = {"csrfmiddlewaretoken": token_value}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.value == token_value


class TestIdentifyCsrfTokenTier2:
    """Tier 2: Fuzzy keyword match (name contains csrf/xsrf/forgery)."""

    def test_identify_token_custom_csrf_field(self) -> None:
        """Custom field with 'csrf' in name → Tier 2 match."""
        params = {"my_csrf_field": "somevalue123456789012"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "my_csrf_field"
        assert match.tier == 2
        assert match.source == "form"

    def test_identify_token_xsrf_keyword(self) -> None:
        """Field with 'xsrf' in name → Tier 2 match."""
        params = {"xsrf_val": "tokenABCDEFGHIJKLMNOP"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "xsrf_val"
        assert match.tier == 2

    def test_identify_token_forgery_keyword(self) -> None:
        """Field with 'forgery' in name → Tier 2 match."""
        params = {"anti_forgery": "ForgeryProtectionToken1234"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "anti_forgery"
        assert match.tier == 2

    def test_identify_token_csrf_keyword_case_insensitive(self) -> None:
        """Fuzzy match is case-insensitive (MY_CSRF_FIELD → Tier 2)."""
        params = {"MY_CSRF_FIELD": "AnyValue12345678901234"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.tier == 2


class TestIdentifyCsrfTokenTier3:
    """Tier 3: High-entropy string detection (length + entropy fallback)."""

    def test_identify_token_high_entropy_long_value(self) -> None:
        """Long, high-entropy value in an unnamed field → Tier 3 match."""
        # Base64-like string — high entropy and > 16 chars
        params = {"hidden_val": "aB3cD4eF5gH6iJ7kL8mN9"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.tier == 3
        assert match.source == "form"

    def test_identify_token_low_entropy_no_tier3_match(self) -> None:
        """Low-entropy value (repeated chars) is NOT picked up by Tier 3."""
        params = {"hidden": "aaaaaaaaaaaaaaaaaaaaaa"}  # all 'a' → H = 0
        match = identify_csrf_token(params)
        assert match is None

    def test_identify_token_short_high_entropy_no_tier3_match(self) -> None:
        """Short value (< 16 chars) is NOT picked up by Tier 3, even if high-entropy."""
        params = {"tok": "Ab1Cd2Ef3"}  # < 16 chars
        match = identify_csrf_token(params)
        assert match is None

    def test_identify_token_exactly_16_chars_triggers_tier3(self) -> None:
        """Value of exactly 16 high-entropy chars qualifies for Tier 3."""
        # "abcdefghijklmnop" has 16 unique chars → H = log₂(16) = 4.0 > 3.5
        params = {"fld": "abcdefghijklmnop"}
        match = identify_csrf_token(params)
        assert match is not None
        assert match.tier == 3


class TestIdentifyCsrfTokenPriority:
    """Tier priority: Tier 1 wins over Tier 2 wins over Tier 3."""

    def test_tier1_wins_over_tier3(self) -> None:
        """When a param matches Tier 1 by name, Tier 3 entropy is irrelevant."""
        params = {
            # Tier 1 candidate
            "csrf_token": "short",
            # Tier 3 candidate (long + high entropy)
            "other_field": "aB3cD4eF5gH6iJ7kL8mN9",
        }
        match = identify_csrf_token(params)
        assert match is not None
        assert match.name == "csrf_token"
        assert match.tier == 1

    def test_tier2_wins_over_tier3(self) -> None:
        """Tier 2 fuzzy match wins over a Tier 3 high-entropy field."""
        params = {
            "my_csrf": "tiny",  # Tier 2 (contains 'csrf')
            "fld": "aB3cD4eF5gH6iJ7kL8mN9",  # Tier 3 candidate
        }
        match = identify_csrf_token(params)
        assert match is not None
        assert match.tier == 2
        assert match.name == "my_csrf"


class TestIdentifyCsrfTokenEdgeCases:
    """Edge cases and degenerate inputs."""

    def test_identify_token_empty_params_returns_none(self) -> None:
        """Empty dict → None (no token found)."""
        assert identify_csrf_token({}) is None

    def test_identify_token_ordinary_form_fields_returns_none(self) -> None:
        """Regular form fields with no CSRF signals → None."""
        params = {"username": "alice", "password": "secret", "remember_me": "1"}
        assert identify_csrf_token(params) is None

    def test_identify_token_returns_token_match_type(self) -> None:
        """Successful identification returns a TokenMatch instance."""
        params = {"csrfmiddlewaretoken": "django_token_value_here"}
        match = identify_csrf_token(params)
        assert isinstance(match, TokenMatch)

    def test_identify_token_custom_entropy_threshold(self) -> None:
        """Custom entropy_threshold kwarg affects Tier 3 triggering."""
        # This value passes at threshold 2.0 but fails at 4.5
        params = {"fld": "1234567890123456"}  # 10 unique chars → H ≈ 3.32
        high_threshold = identify_csrf_token(params, entropy_threshold=4.5)
        low_threshold = identify_csrf_token(params, entropy_threshold=2.0)
        assert high_threshold is None
        assert low_threshold is not None
        assert low_threshold.tier == 3

    def test_identify_token_custom_min_length(self) -> None:
        """Custom min_token_length kwarg affects Tier 3 triggering."""
        params = {"fld": "abcdefgh"}  # 8 chars, 8 unique → H = 3.0
        default_match = identify_csrf_token(params)  # default min_length=16 → None
        short_match = identify_csrf_token(params, min_token_length=8, entropy_threshold=2.0)
        assert default_match is None
        assert short_match is not None


# ===========================================================================
# Header Token Identification
# ===========================================================================


class TestIdentifyCsrfHeader:
    """Tests for identify_csrf_header() — double-submit header pattern."""

    def test_identify_header_x_csrf_token(self) -> None:
        """X-CSRF-Token header → TokenMatch with tier=0, source='header'."""
        headers = {
            "Content-Type": "application/json",
            "X-CSRF-Token": "abc123def456ghi789jkl",
        }
        match = identify_csrf_header(headers)
        assert match is not None
        assert match.name == "X-CSRF-Token"
        assert match.tier == 0
        assert match.source == "header"

    def test_identify_header_x_xsrf_token_angular(self) -> None:
        """X-XSRF-Token (Angular default) → match."""
        headers = {"X-XSRF-Token": "angular_xsrf_value_here_1234"}
        match = identify_csrf_header(headers)
        assert match is not None
        assert match.name == "X-XSRF-Token"

    def test_identify_header_x_csrftoken_django(self) -> None:
        """X-CSRFToken (Django AJAX convention) → match."""
        headers = {"X-CSRFToken": "django_ajax_csrf_value_here"}
        match = identify_csrf_header(headers)
        assert match is not None
        assert match.name == "X-CSRFToken"

    def test_identify_header_case_insensitive(self) -> None:
        """Header matching is case-insensitive."""
        headers = {"x-csrf-token": "LowerCaseHeaderValue1234"}
        match = identify_csrf_header(headers)
        assert match is not None
        assert match.source == "header"

    def test_identify_header_none_when_absent(self) -> None:
        """No CSRF header present → None."""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Bearer sometoken",
        }
        match = identify_csrf_header(headers)
        assert match is None

    def test_identify_header_empty_dict_returns_none(self) -> None:
        """Empty headers dict → None."""
        assert identify_csrf_header({}) is None

    def test_identify_header_value_preserved(self) -> None:
        """Token value from header is preserved in the match."""
        value = "ExactHeaderValue1234567890"
        headers = {"X-CSRF-Token": value}
        match = identify_csrf_header(headers)
        assert match is not None
        assert match.value == value


# ===========================================================================
# parse_form_params helper
# ===========================================================================


class TestParseFormParams:
    """Tests for the parse_form_params() URL-decode helper."""

    def test_parse_simple_body(self) -> None:
        """Simple urlencoded body is parsed into a dict."""
        result = parse_form_params("name=Alice&csrf_token=abc123")
        assert result == {"name": "Alice", "csrf_token": "abc123"}

    def test_parse_empty_body_returns_empty_dict(self) -> None:
        """Empty string → empty dict."""
        assert parse_form_params("") == {}

    def test_parse_none_body_returns_empty_dict(self) -> None:
        """None body → empty dict (GET requests)."""
        assert parse_form_params(None) == {}

    def test_parse_url_encoded_values(self) -> None:
        """URL-encoded characters are decoded."""
        result = parse_form_params("name=Alice+Smith&token=hello%20world")
        assert result["name"] == "Alice Smith"
        assert result["token"] == "hello world"

    def test_parse_duplicate_keys_takes_last(self) -> None:
        """Duplicate keys preserve the last occurrence."""
        result = parse_form_params("key=first&key=second")
        assert result["key"] == "second"
