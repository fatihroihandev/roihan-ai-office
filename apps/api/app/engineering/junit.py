"""Parser laporan JUnit dan ringkasan pytest. Isi berasal dari sandbox, jadi diperlakukan sebagai data tak tepercaya."""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_XML_CHARS = 500_000
MAX_CASES = 500


@dataclass
class Case:
    name: str
    classname: str | None
    outcome: str  # passed | failed | error | skipped
    message: str | None
    duration_ms: int | None


@dataclass
class Summary:
    source: str  # junit | stdout | none
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int | None = None
    cases: list[Case] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.errors or self.source == "none":
            return "error"
        return "failed" if self.failed else ("passed" if self.passed else "error")


def parse_junit(xml_text: str) -> Summary:
    if len(xml_text) > MAX_XML_CHARS:
        raise ValueError("Laporan JUnit terlalu besar")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", xml_text, re.I):
        raise ValueError("Laporan JUnit ditolak: mengandung DOCTYPE/ENTITY")
    root = ET.fromstring(xml_text)
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    cases: list[Case] = []
    total_time = 0.0
    for suite in suites:
        total_time += float(suite.get("time", "0") or 0)
        for tc in suite.iter("testcase"):
            if len(cases) >= MAX_CASES:
                break
            outcome, message = "passed", None
            for child in tc:
                if child.tag in {"failure", "error", "skipped"}:
                    outcome = "failed" if child.tag == "failure" else child.tag
                    message = (child.get("message") or (child.text or "")).strip()[:500] or None
                    break
            t = tc.get("time")
            cases.append(Case(tc.get("name", "?")[:200], tc.get("classname"), outcome, message,
                              int(float(t) * 1000) if t else None))
    count = lambda o: sum(1 for c in cases if c.outcome == o)  # noqa: E731
    return Summary("junit", len(cases), count("passed"), count("failed"), count("error"), count("skipped"),
                   int(total_time * 1000), cases)


_COUNT = re.compile(r"(\d+) (passed|failed|error|errors|skipped)")


def parse_pytest_stdout(stdout: str) -> Summary:
    """Cadangan jika laporan JUnit tidak tersedia: baca baris ringkasan pytest."""
    for line in reversed(stdout.strip().splitlines()):
        found = _COUNT.findall(line)
        if found and ("in " in line or "=" in line or "passed" in line or "failed" in line):
            n = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
            for count, label in found:
                n["error" if label == "errors" else label] += int(count)
            return Summary("stdout", sum(n.values()), n["passed"], n["failed"], n["error"], n["skipped"])
    return Summary("none")
