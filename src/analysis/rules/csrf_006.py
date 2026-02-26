"""CSRF-006: SameSite=None Without Secure.

Re-exports :class:`Csrf006` from ``csrf_005`` where it is co-located
with CSRF-005 since both rules share cookie-parsing helpers.

This module exists so that ``config/rules.yaml``'s ``module: csrf_006``
resolves correctly.

Ref:
    - spec/Requirements.md FR-207
    - config/rules.yaml CSRF-006
    - spec/Tasks.md T-216
"""

from src.analysis.rules.csrf_005 import Csrf006  # noqa: F401
