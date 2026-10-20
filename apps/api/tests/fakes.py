import asyncio

from app.providers.base import (
    GenerateRequest, GenerateResult, HealthResult, ModelInfo, ModelProvider, ProviderError, Usage,
)


class FakeProvider(ModelProvider):
    def __init__(self, name="ollama", is_paid=False, error: ProviderError | None = None, delay: float = 0, reply=None,
                 truncated: bool = False):
        self.name, self.is_paid, self.is_local = name, is_paid, not is_paid
        self.error, self.delay, self.reply, self.truncated = error, delay, reply, truncated
        self.errors: list = []  # antrean error: dipakai satu per panggilan sebelum kembali normal
        self.calls: list[tuple[str, GenerateRequest]] = []
        self.active = self.max_active = 0
        self.models = [ModelInfo("fake-model:1b", context_limit=8192, supports_tools=True, supports_vision=False)]

    async def health_check(self):
        return HealthResult("up", 3, "9.9.9")

    async def list_models(self):
        return self.models

    async def get_capabilities(self, model):
        return next(m for m in self.models if m.model_id == model)

    async def generate(self, model, request):
        self.calls.append((model, request))
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.errors:
                raise self.errors.pop(0)
            if self.error:
                raise self.error
            if callable(self.reply):
                text = self.reply(request.prompt)
            elif isinstance(self.reply, list):
                text = self.reply.pop(0)
            elif isinstance(self.reply, str):
                text = self.reply
            else:
                text = f"jawaban:{request.prompt}"
            return GenerateResult(text, model, Usage(5, 7, 12), truncated=self.truncated)
        finally:
            self.active -= 1

    async def cancel(self, request_id):
        return False
