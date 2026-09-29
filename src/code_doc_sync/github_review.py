import json
import urllib.error
import urllib.request

from code_doc_sync.models import AnalysisReport, ChangePacket, ConsistencyStatus


COMMENT_MARKER = "<!-- code-doc-sync-agent -->"


def render_review(packet: ChangePacket, report: AnalysisReport) -> str:
    rows = (
        ("Jira", report.dashboard.jira),
        ("Confluence", report.dashboard.confluence),
        ("Tests", report.dashboard.tests),
    )
    lines = [
        COMMENT_MARKER,
        "# Delivery Sync Dashboard",
        "",
        f"**Overall:** {_status_badge(report.overall_status)}",
        "",
        report.change_summary,
        "",
        "| Area | Status | What is inconsistent | Required update |",
        "|---|---|---|---|",
        *[
            "| "
            + " | ".join(
                (
                    area,
                    _status_badge(assessment.status),
                    _table_text(assessment.inconsistency),
                    _table_text(assessment.required_update),
                )
            )
            + " |"
            for area, assessment in rows
        ],
        "",
        "> [!NOTE]",
        "> Suggestion only. Jira and Confluence have not been changed.",
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
            "<summary><strong>Proposed Jira update</strong></summary>",
            "",
            f"**Issue:** [{packet.issue.identifier}]({packet.issue.url})  ",
            f"**Suggested status:** {report.jira_suggestion.suggested_status}",
            "",
            "**Suggested comment**",
            "",
            f"> {report.jira_suggestion.comment.replace(chr(10), chr(10) + '> ')}",
            "",
            f"**Rationale:** {report.jira_suggestion.rationale}",
            "",
            "</details>",
            "",
            "<details>",
            "<summary><strong>Proposed Confluence update</strong></summary>",
            "",
            f"**Page:** [{packet.design_document.title}]({packet.design_document.url})",
            "",
            report.confluence_suggestion.summary,
            "",
            *[
                f"- {change}"
                for change in report.confluence_suggestion.proposed_changes
            ],
            "",
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


def _status_badge(status: ConsistencyStatus) -> str:
    label, color = {
        ConsistencyStatus.CONSISTENT: ("aligned", "2da44e"),
        ConsistencyStatus.INCONSISTENT: ("out_of_sync", "cf222e"),
        ConsistencyStatus.MISSING_EVIDENCE: ("evidence_missing", "bf8700"),
    }[status]
    alt = label.replace("_", " ").title()
    return (
        f"![{alt}](https://img.shields.io/badge/status-{label}-{color}"
        "?style=flat-square)"
    )


def _table_text(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")


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
