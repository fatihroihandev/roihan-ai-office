from app.config import Settings
from app.sandbox.base import DisabledSandbox, Sandbox
from app.sandbox.wsl import WslSandbox


def build_sandbox(settings: Settings) -> Sandbox:
    if settings.sandbox_backend == "wsl":
        return WslSandbox(settings.sandbox_wsl_distro)
    return DisabledSandbox()
