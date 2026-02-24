# 🧪 Testing Strategy — CSRF Shield AI

> **Purpose:** Define testing approach, coverage targets, and testing conventions.
> **Last Updated:** February 24, 2026

---

## 1. Testing Framework

- **Framework:** pytest
- **Coverage tool:** pytest-cov
- **Assertions:** Use plain `assert` (pytest will provide detailed diffs)
- **Fixtures:** Shared fixtures in `tests/conftest.py`
- **Mocking:** `unittest.mock` or `pytest-mock`

---

## 2. Test Types

### 2.1 Unit Tests (Per Module)

Each module gets a corresponding test file. Tests are isolated — no external dependencies.

| Source Module                       | Test File                         | Focus                              |
| ----------------------------------- | --------------------------------- | ---------------------------------- |
| `src/input/models.py`               | `tests/test_models.py`            | Dataclass creation, validation     |
| `src/input/har_parser.py`           | `tests/test_har_parser.py`        | HAR parsing, content type handling |
| `src/input/auth_detector.py`        | `tests/test_auth_detector.py`     | Auth mechanism classification      |
| `src/analysis/static_analyzer.py`   | `tests/test_static_analyzer.py`   | Rule orchestration                 |
| `src/analysis/feature_extractor.py` | `tests/test_feature_extractor.py` | Feature extraction                 |
| `src/analysis/rules/csrf_*.py`      | `tests/test_rules.py`             | Individual rule detection          |
| `src/ml/predictor.py`               | `tests/test_ml_predictor.py`      | Inference engine                   |
| `src/ml/heuristics.py`              | `tests/test_heuristics.py`        | Heuristic boost logic              |
| `src/scoring/risk_scorer.py`        | `tests/test_risk_scorer.py`       | Scoring formula                    |
| `src/output/report_generator.py`    | `tests/test_report_generator.py`  | Report output                      |

### 2.2 Integration Tests

End-to-end tests that exercise the full pipeline:

```python
# tests/test_integration.py

def test_full_pipeline_with_vulnerable_har():
    """HAR file with missing CSRF tokens should produce HIGH risk score."""
    result = analyze_har("data/sample_har/vulnerable.har")
    assert result.risk_score >= 41  # HIGH or CRITICAL
    assert any(f.rule_id == "CSRF-001" for f in result.findings)

def test_full_pipeline_with_protected_har():
    """HAR file with proper CSRF protection should produce LOW risk score."""
    result = analyze_har("data/sample_har/protected.har")
    assert result.risk_score <= 20  # LOW

def test_short_circuit_bearer_auth():
    """HAR file with Bearer-only auth should short-circuit to LOW.

    Note: ml_probability is None (not 0.0) because the ML pipeline was
    completely skipped. This is safe because the risk scorer is NEVER
    called for short-circuited flows — the Flow Parser assigns the
    fixed score of 5 directly. The scorer formula (W_ml × ML_Probability)
    is only reached for non-short-circuited flows where ml_probability
    is always a float.
    """
    result = analyze_har("data/sample_har/bearer_auth.har")
    assert result.risk_score == 5
    assert any(f.rule_id == "CSRF-011" for f in result.findings)
    assert result.ml_probability is None  # ML was skipped entirely
    # The risk_scorer.calculate() must NOT be called for this result.
    # If it were, it would crash on W_ml × None. The short-circuit
    # path in flow_parser.py bypasses the scorer completely.
```

### 2.3 Model Tests (Phase 3)

- Evaluate model on held-out test set
- Assert accuracy ≥80%, recall ≥85%
- Test that heuristic boost correctly overrides ML probability

---

## 3. Test Data

### 3.1 Sample HAR Files

Create sample HAR files in `data/sample_har/` for testing:

| File                   | Description                                        | Expected Result     |
| ---------------------- | -------------------------------------------------- | ------------------- |
| `vulnerable.har`       | POST form without CSRF token                       | HIGH/CRITICAL       |
| `protected.har`        | POST form with valid CSRF token + SameSite         | LOW                 |
| `bearer_auth.har`      | Requests with only Authorization: Bearer header    | LOW (short-circuit) |
| `api_key.har`          | Requests with X-API-Key header only                | LOW (short-circuit) |
| `mixed_auth.har`       | Both cookies and Bearer header                     | Analyze normally    |
| `multipart.har`        | File upload form with CSRF token in multipart body | LOW                 |
| `static_token.har`     | Same CSRF token across multiple requests           | HIGH/CRITICAL       |
| `get_state_change.har` | GET request to /delete endpoint                    | HIGH                |

### 3.2 Fixtures

Common fixtures in `tests/conftest.py`:

```python
@pytest.fixture
def sample_exchange():
    """A basic HTTP exchange for unit testing."""
    return HttpExchange(
        request_method="POST",
        request_url="https://example.com/profile/update",
        request_headers={"Content-Type": "application/x-www-form-urlencoded"},
        request_cookies={"session_id": "abc123"},
        request_body="name=test&csrf_token=randomtoken123456",
        request_content_type="application/x-www-form-urlencoded",
        response_status=200,
        response_headers={"Set-Cookie": "session_id=abc123; SameSite=Lax"},
        response_body="<html>OK</html>",
        timestamp=datetime.now(),
    )

@pytest.fixture
def sample_session_flow(sample_exchange):
    """A session flow containing one exchange."""
    return SessionFlow(
        session_id="test-session",
        exchanges=[sample_exchange],
        auth_mechanism="cookie",
    )
```

---

## 4. Coverage Targets

| Module Category       | Target Coverage |
| --------------------- | --------------- |
| Core models           | ≥95%            |
| HAR parser            | ≥90%            |
| Auth detector         | ≥95%            |
| Static analysis rules | ≥90%            |
| Feature extractor     | ≥85%            |
| Risk scorer           | ≥95%            |
| ML inference          | ≥80%            |
| Report generator      | ≥75%            |
| **Overall**           | **≥80%**        |

---

## 5. Running Tests

```shell
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_har_parser.py -v

# Run tests matching a pattern
pytest tests/ -k "test_multipart" -v
```

---

## 6. Test Naming Convention

```
test_<function_name>_<scenario>_<expected_result>
```

Examples:

- `test_parse_har_valid_file_returns_exchanges()`
- `test_detect_auth_bearer_only_returns_header_only()`
- `test_risk_scorer_high_ml_prob_returns_critical()`
- `test_identify_token_custom_name_uses_entropy_fallback()`

---

_Write tests as you implement features. Never defer testing to a later phase._
