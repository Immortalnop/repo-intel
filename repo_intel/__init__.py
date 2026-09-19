"""Git Repository Intelligence — software health analytics from Git history.

Deterministic analytics (churn, ownership, bug-proneness, drift, knowledge
concentration, release readiness) run with NO AI. A local LLM (e.g. Qwen) is an
optional narrative layer that defaults to a no-op provider.
"""

__version__ = "1.0.0"

from .report.builder import analyze  # noqa: F401
