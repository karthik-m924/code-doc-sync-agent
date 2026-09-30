import base64
import hashlib
import json
import re
import urllib.error
import urllib.request

from code_doc_sync.models import (
    AnalysisReport,
    ApprovalPlan,
    ChangePacket,
    ConsistencyStatus,
)


COMMENT_MARKER = "<!-- code-doc-sync-agent -->"
PLAN_MARKER_PATTERN = re.compile(r"<!-- code-doc-sync-plan:([A-Za-z0-9_-]+) -->")
APPLIED_MARKER_PREFIX = "<!-- code-doc-sync-applied:"


def render_review(packet: ChangePacket, report: AnalysisReport) -> str:
    plan = ApprovalPlan(
        pull_number=packet.code_change.pull_request_number or 0,
        head_sha=packet.code_change.commit_sha,
        jira_issue_key=packet.issue.identifier,
        confluence_page_id=packet.design_document.identifier,
        jira_suggestion=report.jira_suggestion,
        confluence_suggestion=report.confluence_suggestion,
    )
    encoded_plan = encode_plan(plan)
    plan_id = approval_plan_id(plan)
    repository = packet.code_change.repository
    workflow_url = (
        f"https://github.com/{repository}/actions/workflows/code-doc-sync.yml"
    )
    code_changes = "<br>".join(
        f"{index}. {_table_text(change)}"
        for index, change in enumerate(report.dashboard.code.changes, start=1)
    )
    rows = (
        (
            "Code",
            _status_badge(
                report.dashboard.code.status, aligned_label="implemented"
            ),
            code_changes,
            _table_text(report.dashboard.code.next_step),
        ),
        *[
            (
                area,
                _status_badge(assessment.status),
                _table_text(
                    assessment.summary
                    if assessment.status == ConsistencyStatus.CONSISTENT
                    else assessment.inconsistency
                ),
                _table_text(assessment.required_update),
            )
            for area, assessment in (
                ("Jira", report.dashboard.jira),
                ("Confluence", report.dashboard.confluence),
                ("Tests", report.dashboard.tests),
            )
        ],
    )
    lines = [
        COMMENT_MARKER,
        f"<!-- code-doc-sync-plan:{encoded_plan} -->",
        "# PR Change Impact Review",
        "",
        f"**Overall:** {_status_badge(report.overall_status, inconsistent_label='action_required')}",
        "",
        report.change_summary,
        "",
        "| Area | Status | What we found | Next step |",
        "|---|---|---|---|",
        *[
            "| "
            + " | ".join(
                (
                    area,
                    status,
                    finding,
                    next_step,
                )
            )
            + " |"
            for area, status, finding, next_step in rows
        ],
        "",
        "> [!NOTE]",
        "> Suggestion only. Jira and Confluence have not been changed.",
        "",
        "## Apply recommended changes",
        "",
        f"[![Apply changes](https://img.shields.io/badge/Apply_recommended_changes-0969da?style=for-the-badge)]({workflow_url})",
        "",
        "Open the workflow, choose **Run workflow**, and enter:",
        f"- **Pull request number:** `{plan.pull_number}`",
        f"- **Plan ID:** `{plan_id}`",
        "",
        "> The plan is applied only if this PR still points to the reviewed commit.",
        "",
        "<details>",
        f"<summary><strong>Detailed findings and evidence ({len(report.findings)})</strong></summary>",
        "",
    ]
    for finding in report.findings:
        lines.extend(
            [
                f"#### {finding.title}",
                f"**Severity:** {finding.severity.value.title()}  ",
                f"**Status:** {_status_badge(finding.status)}",
                "",
                finding.explanation,
                "",
                "**Evidence**",
                *[f"- {item}" for item in finding.evidence],
                "",
                f"**Recommended action:** {finding.recommended_action}",
                "",
            ]
        )
    lines.extend(["</details>", ""])

    lines.extend(
        [
            "<details>",
            "<summary><strong>Copy-ready Jira update</strong></summary>",
            "",
            f"**Issue:** [{packet.issue.identifier}]({packet.issue.url})  ",
            f"**Suggested status:** {report.jira_suggestion.suggested_status}",
            "",
            "**Comment to paste**",
            "",
            _code_block(report.jira_suggestion.comment),
            "",
            "**Acceptance checklist to paste**",
            "",
            _code_block(
                "\n".join(
                    f"- [ ] {item}"
                    for item in report.jira_suggestion.acceptance_checklist
                )
            ),
            "",
            f"**Rationale:** {report.jira_suggestion.rationale}",
            "",
            "</details>",
            "",
            "<details>",
            (
                "<summary><strong>Copy-ready Confluence updates "
                f"({len(report.confluence_suggestion.section_updates)} sections)"
                "</strong></summary>"
            ),
            "",
            f"**Page:** [{packet.design_document.title}]({packet.design_document.url})",
            "",
            report.confluence_suggestion.summary,
            "",
        ]
    )
    for update in report.confluence_suggestion.section_updates:
        lines.extend(
            [
                f"#### {update.section}",
                f"**Action:** {update.operation.title()}",
                "",
                _code_block(update.content, language="markdown"),
                "",
            ]
        )
    lines.extend(
        [
            "</details>",
            "",
            "<details>",
            "<summary><strong>Recommended actions</strong></summary>",
            "",
            *[f"- {action}" for action in report.recommended_actions],
            "",
            "</details>",
        ]
    )
    return "\n".join(lines)


def approval_plan_id(plan: ApprovalPlan) -> str:
    payload = plan.model_dump_json(exclude_none=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def encode_plan(plan: ApprovalPlan) -> str:
    payload = plan.model_dump_json(exclude_none=True).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_plan(body: str) -> ApprovalPlan:
    match = PLAN_MARKER_PATTERN.search(body)
    if not match:
        raise ValueError("The PR review does not contain an approval plan.")
    encoded = match.group(1)
    encoded += "=" * (-len(encoded) % 4)
    return ApprovalPlan.model_validate_json(base64.urlsafe_b64decode(encoded))


def _status_badge(
    status: ConsistencyStatus,
    *,
    aligned_label: str = "aligned",
    inconsistent_label: str = "needs_update",
) -> str:
    label, color = {
        ConsistencyStatus.CONSISTENT: (aligned_label, "2da44e"),
        ConsistencyStatus.INCONSISTENT: (inconsistent_label, "cf222e"),
        ConsistencyStatus.MISSING_EVIDENCE: ("evidence_missing", "bf8700"),
    }[status]
    alt = label.replace("_", " ").title()
    return (
        f"![{alt}](https://img.shields.io/badge/-{label}-{color}"
        "?style=flat-square)"
    )


def _table_text(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


def _code_block(value: str, *, language: str = "text") -> str:
    return f"````{language}\n{value.strip()}\n````"


def upsert_pull_request_comment(
    *,
    token: str,
    owner: str,
    repo: str,
    pull_number: int,
    body: str,
) -> None:
    base_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "code-doc-sync-agent",
    }
    comments = _request_json(
        f"{base_url}/issues/{pull_number}/comments?per_page=100", headers
    )
    existing = next(
        (
            comment
            for comment in comments
            if COMMENT_MARKER in comment.get("body", "")
        ),
        None,
    )
    if existing:
        _request_json(
            f"{base_url}/issues/comments/{existing['id']}",
            headers,
            method="PATCH",
            payload={"body": body},
        )
    else:
        _request_json(
            f"{base_url}/issues/{pull_number}/comments",
            headers,
            method="POST",
            payload={"body": body},
        )


def get_pull_request_comment(
    *, token: str, owner: str, repo: str, pull_number: int
) -> str:
    headers = _github_headers(token)
    comments = _request_json(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{pull_number}/comments?per_page=100",
        headers,
    )
    existing = next(
        (comment for comment in comments if COMMENT_MARKER in comment.get("body", "")),
        None,
    )
    if not existing:
        raise ValueError("No Code-Doc Sync review was found on this pull request.")
    return existing["body"]


def get_pull_request_head_sha(
    *, token: str, owner: str, repo: str, pull_number: int
) -> str:
    pull = _request_json(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}",
        _github_headers(token),
    )
    return pull["head"]["sha"]


def has_applied_plan(
    *, token: str, owner: str, repo: str, pull_number: int, plan_id: str
) -> bool:
    comments = _request_json(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{pull_number}/comments?per_page=100",
        _github_headers(token),
    )
    marker = f"{APPLIED_MARKER_PREFIX}{plan_id} -->"
    return any(marker in comment.get("body", "") for comment in comments)


def post_pull_request_comment(
    *, token: str, owner: str, repo: str, pull_number: int, body: str
) -> None:
    _request_json(
        f"https://api.github.com/repos/{owner}/{repo}/issues/{pull_number}/comments",
        _github_headers(token),
        method="POST",
        payload={"body": body},
    )


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "code-doc-sync-agent",
    }


def _request_json(
    url: str,
    headers: dict[str, str],
    *,
    method: str = "GET",
    payload: dict[str, str] | None = None,
):
    data = json.dumps(payload).encode("utf-8") if payload else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub comment request failed ({exc.code}): {detail}") from exc
