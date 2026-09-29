import json
import urllib.error
import urllib.request

from code_doc_sync.models import AnalysisReport, ChangePacket


COMMENT_MARKER = "<!-- code-doc-sync-agent -->"


def render_review(packet: ChangePacket, report: AnalysisReport) -> str:
    status = report.overall_status.value.replace("_", " ").upper()
    lines = [
        COMMENT_MARKER,
        "# Code-Doc Sync Review",
        "",
        f"**Result:** {status}",
        "",
        report.change_summary,
        "",
        "## Findings",
        "",
    ]
    for finding in report.findings:
        lines.extend(
            [
                f"### {finding.title}",
                f"**Severity:** {finding.severity.value.title()}  ",
                f"**Status:** {finding.status.value.replace('_', ' ').title()}",
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

    lines.extend(
        [
            "## Proposed Jira Update",
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
            "## Proposed Confluence Update",
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
            "## Recommended Actions",
            "",
            *[f"- {action}" for action in report.recommended_actions],
            "",
            "_Suggestion only. No Jira or Confluence content was changed._",
        ]
    )
    return "\n".join(lines)


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
