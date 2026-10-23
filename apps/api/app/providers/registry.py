from dataclasses import dataclass

from app.config import Settings
from app.providers.base import ModelProvider
from app.providers.cloud import AnthropicProvider, GeminiProvider, OpenAIProvider
from app.providers.ollama import OllamaProvider


@dataclass
class ProviderEntry:
    name: str
    kind: str          # "local" | "cloud"
    is_paid: bool
    enabled: bool
    implemented: bool  # adapter tersedia
    provider: ModelProvider | None = None


class ProviderRegistry:
    def __init__(self, entries: list[ProviderEntry]):
        self._entries = {e.name: e for e in entries}

    def get(self, name: str) -> ProviderEntry | None:
        return self._entries.get(name)

    def all(self) -> list[ProviderEntry]:
        return list(self._entries.values())


CLOUD = ("openai", "gemini", "anthropic")


def build_registry(settings: Settings, overrides: dict[str, ModelProvider] | None = None) -> ProviderRegistry:
    """Bangun registry adapter provider lokal dan cloud."""
    entries = [ProviderEntry(
        "ollama", "local", False, settings.ollama_enabled, True,
        OllamaProvider(settings.ollama_base_url, settings.ollama_timeout_s),
    )]
    cloud = {"openai": OpenAIProvider, "gemini": GeminiProvider, "anthropic": AnthropicProvider}
    entries += [ProviderEntry(n, "cloud", True, getattr(settings, f"{n}_enabled"), True,
                              cloud[n](getattr(settings, f"{n}_api_key"))) for n in CLOUD]
    registry = ProviderRegistry(entries)
    for name, provider in (overrides or {}).items():  # dipakai tes untuk menyuntikkan provider palsu
        e = registry.get(name) or ProviderEntry(name, "local" if provider.is_local else "cloud", provider.is_paid, True, True)
        e.provider, e.implemented, e.is_paid = provider, True, provider.is_paid
        if registry.get(name) is None:
            registry._entries[name] = e
    return registry
