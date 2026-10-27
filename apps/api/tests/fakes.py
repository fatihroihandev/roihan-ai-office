import asyncio

from app.sandbox.base import ExecResult, ExecSpec, Sandbox, SandboxStatus
from app.providers.base import (
    GenerateRequest, GenerateResult, HealthResult, ModelInfo, ModelProvider, ProviderError, Usage,
)


class FakeProvider(ModelProvider):
    def __init__(self, name="ollama", is_paid=False, error: ProviderError | None = None, delay: float = 0, reply=None,
                 truncated: bool | list[bool] = False):
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
                text = self.reply.pop(0) if self.reply else (getattr(self, "default_reply", None) or f"jawaban:{request.prompt}")
            elif isinstance(self.reply, str):
                text = self.reply
            else:
                text = f"jawaban:{request.prompt}"
            truncated = self.truncated.pop(0) if (isinstance(self.truncated, list) and self.truncated) else bool(self.truncated)
            return GenerateResult(text, model, Usage(5, 7, 12), truncated=truncated)
        finally:
            self.active -= 1

    async def cancel(self, request_id):
        return False


# ------------------------------------------------------------------ sandbox palsu

def junit_xml(passed=(), failed=()) -> str:
    cases = "".join(f'<testcase classname="tests.test_x" name="{n}" time="0.01"/>' for n in passed)
    cases += "".join(f'<testcase classname="tests.test_x" name="{n}" time="0.01"><failure message="{m}">tb</failure></testcase>'
                     for n, m in failed)
    total = len(passed) + len(failed)
    return f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{total}" time="0.05">{cases}</testsuite></testsuites>'


def pytest_ok(*names, stdout=None) -> ExecResult:
    names = names or ("test_a",)
    return ExecResult(0, stdout or f"{len(names)} passed in 0.05s", "", 120, collected=junit_xml(passed=names))


def pytest_fail(failed=(("test_add", "assert 3 == 4"),), passed=("test_ok",)) -> ExecResult:
    return ExecResult(1, f"{len(failed)} failed, {len(passed)} passed in 0.05s", "", 130,
                      collected=junit_xml(passed=passed, failed=failed))


OK_COMPILE = ExecResult(0, "", "", 30)


class FakeSandbox(Sandbox):
    """Sandbox palsu: hasil per jenis perintah diambil dari antrean (elemen terakhir diulang)."""

    name = "fake"

    def __init__(self, compile=None, pytest=None, available=True, reason="sandbox_disabled", message="Sandbox tidak tersedia"):
        self.script = {"compile": list(compile or [OK_COMPILE]), "pytest": list(pytest or [pytest_ok()])}
        self.available, self.reason, self.message = available, reason, message
        self.runs: list[ExecSpec] = []

    async def status(self):
        return SandboxStatus(self.available, self.name, None if self.available else self.reason,
                             None if self.available else self.message)

    async def run(self, spec):
        self.runs.append(spec)
        kind = "pytest" if "pytest" in spec.argv else "compile" if "compileall" in spec.argv else "other"
        queue = self.script.get(kind) or [ExecResult(0, "", "", 1)]
        return queue.pop(0) if len(queue) > 1 else queue[0]
