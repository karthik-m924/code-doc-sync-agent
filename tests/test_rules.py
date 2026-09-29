from code_doc_sync.models import ChangePacket, ChangedFile, CodeChange, Evidence
from code_doc_sync.rules import run_rules


def _packet(*, message: str, changed_paths: list[str]) -> ChangePacket:
    return ChangePacket(
        issue=Evidence(
            source="jira",
            identifier="SCRUM-5",
            title="Add a field",
            content="Add preferredLanguage.",
        ),
        design_document=Evidence(
            source="confluence",
            identifier="425985",
            title="Design",
            content="Current response contract.",
        ),
        code_change=CodeChange(
            repository="owner/repo",
            commit_sha="abc123",
            commit_message=message,
            files=[ChangedFile(path=path, status="modified") for path in changed_paths],
        ),
    )


def test_flags_implementation_change_without_test_change() -> None:
    findings = run_rules(
        _packet(
            message="SCRUM-5 Add preferred language",
            changed_paths=["src/main/transform.dwl"],
        )
    )

    by_rule = {finding.rule: finding.status.value for finding in findings}
    assert by_rule == {
        "issue-key-in-commit": "consistent",
        "tests-change-with-implementation": "inconsistent",
        "required-evidence-present": "consistent",
    }


def test_accepts_linked_commit_with_test_change() -> None:
    findings = run_rules(
        _packet(
            message="SCRUM-5 Add preferred language",
            changed_paths=["src/main/transform.dwl", "src/test/transform-test.xml"],
        )
    )

    assert all(finding.status.value == "consistent" for finding in findings)
