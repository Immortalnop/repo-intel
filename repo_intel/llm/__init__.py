"""Optional LLM layer. Defaults to NullProvider (rule-based, no AI)."""

from .base import LLMProvider  # noqa: F401
from .caching import CachingProvider  # noqa: F401
from .null_provider import NullProvider  # noqa: F401
from .qwen_local import QwenLocalProvider  # noqa: F401


def get_provider(name: str = "auto", cache: bool = True) -> LLMProvider:
    """Return a provider.

    'none' => NullProvider; 'auto'/'qwen' => local Qwen if reachable, else Null.
    When `cache` is True the result is wrapped in a CachingProvider so an
    unchanged report is not re-summarized by the model.
    """
    name = (name or "auto").lower()
    if name in ("none", "null", "off"):
        base: LLMProvider = NullProvider()
    else:
        prov = QwenLocalProvider()
        base = prov if (name in ("qwen", "local", "auto") and prov.available()) else NullProvider()
    return CachingProvider(base) if cache else base
