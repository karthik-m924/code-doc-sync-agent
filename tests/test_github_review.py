from code_doc_sync.collect import derive_issue_key
from code_doc_sync.connectors.atlassian import apply_section_update
from code_doc_sync.github_review import (
    COMMENT_MARKER,
    approval_plan_id,
    decode_plan,
    render_review,
)
from code_doc_sync.models import (
    AnalysisReport,
    AreaAssessment,
    ChangePacket,
    CodeAssessment,
    CodeChange,
    ConfluenceSectionUpdate,
    ConfluenceSuggestion,
    ConsistencyFinding,
    ConsistencyStatus,
    Evidence,
    JiraSuggestion,
    Severity,
    SyncDashboard,
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
            pull_request_number=7,
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
        dashboard=SyncDashboard(
            code=CodeAssessment(
                status=ConsistencyStatus.CONSISTENT,
                changes=[
                    "Added preferredLanguage to the Customer Profile response.",
                    "Mapped it from preferred_language with an en default.",
                ],
                next_step="No code change is required.",
            ),
            jira=AreaAssessment(
                status=ConsistencyStatus.INCONSISTENT,
                summary="Work remains.",
                inconsistency="The story is not ready to close.",
                required_update="Add the suggested comment and retain In Progress.",
            ),
            confluence=AreaAssessment(
                status=ConsistencyStatus.INCONSISTENT,
                summary="Design is stale.",
                inconsistency="preferredLanguage is absent.",
                required_update="Add the field and fallback behavior.",
            ),
            tests=AreaAssessment(
                status=ConsistencyStatus.MISSING_EVIDENCE,
                summary="Coverage is incomplete.",
                inconsistency="Required cases are absent.",
                required_update="Add present, missing, and null cases.",
            ),
        ),
        jira_suggestion=JiraSuggestion(
            comment="Implementation found; documentation and tests need updates.",
            suggested_status="In Progress",
            rationale="Acceptance criteria are not fully evidenced.",
            acceptance_checklist=[
                "Add tests for present and missing preferred_language values.",
                "Update the technical design.",
            ],
        ),
        confluence_suggestion=ConfluenceSuggestion(
            summary="Document the new response field.",
            proposed_changes=["Add preferredLanguage to the response example."],
            section_updates=[
                ConfluenceSectionUpdate(
                    section="Current response structure",
                    operation="replace",
                    content='{"preferredLanguage": "en"}',
                ),
                ConfluenceSectionUpdate(
                    section="Field mappings",
                    operation="add",
                    content="| preferredLanguage | preferred_language | Defaults to en |",
                ),
            ],
        ),
    )

    review = render_review(packet, report)

    assert COMMENT_MARKER in review
    assert "# PR Change Impact Review" in review
    assert "| Code |" in review
    assert "Added preferredLanguage" in review
    assert "| Area | Status | What we found | Next step |" in review
    assert "| Jira |" in review
    assert "| Confluence |" in review
    assert "| Tests |" in review
    assert "<summary><strong>Copy-ready Jira update</strong></summary>" in review
    assert "**Suggested status:** In Progress" in review
    assert "**Acceptance checklist to paste**" in review
    assert "Copy-ready Confluence updates (2 sections)" in review
    assert "#### Current response structure" in review
    assert '````markdown\n{"preferredLanguage": "en"}\n````' in review
    assert "Suggestion only" in review
    assert "Apply recommended changes" in review
    assert "**Pull request number:** `7`" in review
    plan = decode_plan(review)
    assert plan.pull_number == 7
    assert plan.head_sha == "abc123"
    assert approval_plan_id(plan) in review


def test_section_updates_are_scoped_and_strip_outer_fences() -> None:
    content = "# Design\n\n## Response\n\nOld value\n\n## Tests\n\nKeep me\n"
    update = ConfluenceSectionUpdate(
        section="Response",
        operation="replace",
        content='```json\n{"preferredLanguage": "en"}\n```',
    )

    updated = apply_section_update(content, update)

    assert '## Response\n\n{"preferredLanguage": "en"}' in updated
    assert "```" not in updated
    assert "## Tests\n\nKeep me" in updated
