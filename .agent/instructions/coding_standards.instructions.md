# 📐 Coding Standards — CSRF Shield AI

> **Purpose:** Ensure consistent code quality throughout the project.
> **Last Updated:** February 24, 2026

---

## 1. Python Style

### 1.1 General

- **Python version:** 3.10+ (use modern syntax: `match/case`, `X | Y` union types, etc.)
- **Style guide:** PEP 8 with 100-character line limit
- **Formatter:** `black` with `--line-length 100`
- **Linter:** `flake8` + `mypy` for type checking
- **Import order:** `isort` with profile `black`

### 1.2 Naming Conventions

| Element | Convention | Example |
| --- | --- | --- |
| Modules | `snake_case` | `har_parser.py` |
| Classes | `PascalCase` | `HttpExchange` |
| Functions | `snake_case` | `detect_auth_mechanism()` |
| Constants | `UPPER_SNAKE_CASE` | `CUSTOM_AUTH_HEADERS` |
| Private | Leading underscore | `_parse_multipart()` |
| Type hints | Always include | `def foo(x: int) -> str:` |

### 1.3 Docstrings

All public functions and classes **must** have Google-style docstrings:

```python
def detect_auth_mechanism(session_flow: SessionFlow) -> str:
    """Classify the authentication mechanism used in a session flow.

    Analyzes request headers and cookies across all exchanges in the flow
    to determine the primary authentication method.

    Args:
        session_flow: The session flow to analyze.

    Returns:
        One of: 'cookie', 'header_only', 'mixed', 'none'.

    Raises:
        ValueError: If session_flow contains no exchanges.
    """
```

### 1.4 Type Hints

- Use `from __future__ import annotations` for modern type syntax
- Use `Optional[X]` for nullable values
- Use `TypeAlias` for complex types
- Prefer `dataclass` over plain dicts for structured data

---

## 2. Project Conventions

### 2.1 Error Handling

- **Never silently swallow exceptions** — at minimum, log them
- Use specific exception types, not bare `except:`
- For analysis failures, degrade gracefully (return `inconclusive` rather than crash)
- Validation errors should raise `ValueError` with descriptive messages

### 2.2 Logging

- Use `logging` module (not `print()`)
- Log levels: `DEBUG` for trace, `INFO` for progress, `WARNING` for degraded, `ERROR` for failures
- Include context in log messages: `logger.info("Parsed %d exchanges from HAR file", count)`

### 2.3 Configuration

- All configurable values go in `config/settings.yaml` or `config/rules.yaml`
- No hardcoded magic numbers in analysis code
- Default values should be sensible without any config file

### 2.4 Data Models

- Use `@dataclass` for structured data (immutable where possible: `frozen=True`)
- Use `Enum` for fixed categories (severity levels, risk levels, auth mechanisms)
- Use Pydantic only if runtime validation is needed (prefer dataclasses for simplicity)

---

## 3. File Organization

### 3.1 Module Rules

- Each module should have a single responsibility
- Each CSRF rule gets its own file (`csrf_001.py`, `csrf_002.py`, etc.)
- Shared utilities go in a `utils/` package or at module level
- Keep imports at the top of the file

### 3.2 Test Files

- Mirror source structure: `src/input/har_parser.py` → `tests/test_har_parser.py`
- Use descriptive test names: `test_parse_multipart_body_extracts_csrf_token()`
- Each test should test one thing
- Use pytest fixtures for common setup

---

## 4. Dependencies

- Add all dependencies to `requirements.txt` with pinned versions
- Separate dev dependencies in `requirements-dev.txt`
- Don't add dependencies without justification
- Prefer standard library solutions when feasible

---

*Follow these standards in all code. When in doubt, prioritize readability over cleverness.*
