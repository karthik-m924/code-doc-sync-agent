from code_doc_sync.collect import derive_issue_key
from code_doc_sync.github_review import COMMENT_MARKER, render_review
from code_doc_sync.models import (
    AnalysisReport,
    ChangePacket,
    CodeChange,
    ConfluenceSuggestion,
    ConsistencyFinding,
    ConsistencyStatus,
    Evidence,
    JiraSuggestion,
    Severity,
)


def test_derives_issue_key_from_feature_branch() -> None:
    change = CodeChange(
        repository="owner/repo",
        commit_sha="abc123",
        commit_message="Add preferred language",
        head_ref="feature/SCRUM-5-preferred-language",
    )

    assert derive_issue_key(change) == "SCRUM-5"


def test_review_contains_human_approval_proposals() -> None:
    packet = ChangePacket(
        issue=Evidence(
            source="jira",
            identifier="SCRUM-5",
            title="Preferred language",
            url="https://example.test/browse/SCRUM-5",
            content="Requirement",
        ),
        design_document=Evidence(
            source="confluence",
            identifier="425985",
            title="Customer Profile API",
            url="https://example.test/wiki/425985",
            content="Design",
        ),
        code_change=CodeChange(
            repository="owner/repo",
            commit_sha="abc123",
            commit_message="SCRUM-5 Add preferred language",
        ),
    )
    report = AnalysisReport(
        overall_status=ConsistencyStatus.INCONSISTENT,
        change_summary="Code and documentation differ.",
        findings=[
            ConsistencyFinding(
                title="Design is stale",
                severity=Severity.MEDIUM,
                status=ConsistencyStatus.INCONSISTENT,
                explanation="The new field is missing.",
                evidence=["The response example omits preferredLanguage."],
                recommended_action="Update the design.",
            )
        ],
        recommended_actions=["Update documentation and tests."],
        jira_suggestion=JiraSuggestion(
            comment="Implementation found; documentation and tests need updates.",
            suggested_status="In Progress",
            rationale="Acceptance criteria are not fully evidenced.",
        ),
        confluence_suggestion=ConfluenceSuggestion(
            summary="Document the new response field.",
            proposed_changes=["Add preferredLanguage to the response example."],
        ),
    )

    review = render_review(packet, report)

    assert COMMENT_MARKER in review
    assert "## Proposed Jira Update" in review
    assert "**Suggested status:** In Progress" in review
    assert "## Proposed Confluence Update" in review
    assert "Suggestion only" in review
