from code_doc_sync.config import Settings
from code_doc_sync.connectors.atlassian import AtlassianConnector
from code_doc_sync.connectors.github import GitHubConnector
from code_doc_sync.models import ChangePacket


def derive_issue_key(code_change) -> str:
    import re

    candidates = " ".join(
        filter(
            None,
            (
                code_change.pull_request_title,
                code_change.head_ref,
                code_change.commit_message,
            ),
        )
    )
    match = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", candidates.upper())
    if not match:
        raise ValueError(
            "No Jira key was found in the pull-request title or feature branch."
        )
    return match.group(1)


async def collect_pull_request_packet(
    settings: Settings, pull_number: int
) -> ChangePacket:
    github = GitHubConnector(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
    )
    code_change, tests = await github.collect_pull_request(
        pull_number, settings.github_test_paths
    )
    issue_key = derive_issue_key(code_change)
    atlassian = AtlassianConnector(
        site_url=settings.atlassian_site_url,
        email=settings.atlassian_email,
        token=settings.atlassian_api_token,
        jira_project=issue_key.split("-", 1)[0],
        confluence_space="MAD",
    )
    issue, design_document = await atlassian.collect(
        issue_key, settings.confluence_page_id
    )
    return ChangePacket(
        issue=issue,
        design_document=design_document,
        code_change=code_change,
        test_artifacts=tests,
    )


async def collect_change_packet(settings: Settings) -> ChangePacket:
    atlassian = AtlassianConnector(
        site_url=settings.atlassian_site_url,
        email=settings.atlassian_email,
        token=settings.atlassian_api_token,
        jira_project=settings.jira_issue_key.split("-", 1)[0],
        confluence_space="MAD",
    )
    github = GitHubConnector(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
    )
    issue, design_document = await atlassian.collect(
        settings.jira_issue_key, settings.confluence_page_id
    )
    code_change, tests = await github.collect(
        settings.github_commit_sha,
        settings.github_ref,
        settings.github_test_paths,
    )
    return ChangePacket(
        issue=issue,
        design_document=design_document,
        code_change=code_change,
        test_artifacts=tests,
    )
