import pytest

from app.engineering.junit import MAX_XML_CHARS, parse_junit, parse_pytest_stdout
from app.engineering.recorder import summarize
from app.sandbox.base import ExecResult
from tests.fakes import junit_xml


def test_parse_junit_counts_and_messages():
    s = parse_junit(junit_xml(passed=["a", "b"], failed=[("c", "assert 1 == 2")]))
    assert (s.source, s.total, s.passed, s.failed, s.errors, s.skipped) == ("junit", 3, 2, 1, 0, 0)
    assert s.status == "failed" and s.duration_ms == 50
    bad = [c for c in s.cases if c.outcome == "failed"]
    assert bad[0].name == "c" and bad[0].message == "assert 1 == 2" and bad[0].classname == "tests.test_x"


def test_parse_junit_error_and_skipped_cases():
    xml = ('<testsuite time="0.1"><testcase name="e"><error message="boom">tb</error></testcase>'
           '<testcase name="s"><skipped message="nanti"/></testcase><testcase name="ok"/></testsuite>')
    s = parse_junit(xml)
    assert (s.passed, s.errors, s.skipped, s.failed) == (1, 1, 1, 0) and s.status == "error"


def test_all_passed_is_the_only_passing_status():
    assert parse_junit(junit_xml(passed=["a"])).status == "passed"
    assert parse_junit(junit_xml()).status == "error"          # nol tes bukan bukti keberhasilan


@pytest.mark.parametrize("xml", [
    '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><testsuite><testcase name="&a;"/></testsuite>',
    "<!DOCTYPE testsuite><testsuite/>",
    "<!ENTITY x 'y'><testsuite/>",
])
def test_hostile_xml_is_rejected(xml):
    with pytest.raises(ValueError):
        parse_junit(xml)


def test_oversized_and_malformed_xml_rejected():
    with pytest.raises(ValueError):
        parse_junit("<a>" + "x" * MAX_XML_CHARS + "</a>")
    with pytest.raises(Exception):
        parse_junit("<testsuite><testcase")


def test_parse_pytest_stdout_fallback():
    s = parse_pytest_stdout("..F\nFAILED tests/test_a.py::test_x\n1 failed, 2 passed in 0.12s")
    assert (s.source, s.passed, s.failed, s.total) == ("stdout", 2, 1, 3)
    assert parse_pytest_stdout("3 passed in 0.01s").status == "passed"
    assert parse_pytest_stdout("2 passed, 1 error in 0.1s").status == "error"
    assert parse_pytest_stdout("tidak ada ringkasan").status == "error"
    assert parse_pytest_stdout("").source == "none"


def test_summarize_prefers_junit_then_falls_back():
    good = ExecResult(0, "9 passed", "", 1, collected=junit_xml(passed=["a"]))
    assert summarize(good).source == "junit" and summarize(good).total == 1
    assert summarize(ExecResult(0, "3 passed in 0.1s", "", 1, collected=None)).source == "stdout"
    hostile = ExecResult(0, "3 passed in 0.1s", "", 1, collected="<!DOCTYPE x><testsuite/>")
    assert summarize(hostile).source == "stdout"
    broken = ExecResult(1, "1 failed in 0.1s", "", 1, collected="<testsuite><testcase")
    assert summarize(broken).failed == 1
