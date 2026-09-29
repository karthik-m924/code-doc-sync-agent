import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    github_token: str
    github_owner: str
    github_repo: str
    github_commit_sha: str
    github_ref: str
    github_test_paths: tuple[str, ...]
    atlassian_site_url: str
    atlassian_email: str
    atlassian_api_token: str
    jira_issue_key: str
    confluence_page_id: str


def load_settings() -> Settings:
    load_dotenv()
    settings = Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-6-sol"),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_owner=os.getenv("GITHUB_OWNER", "karthik-m924"),
        github_repo=os.getenv("GITHUB_REPO", "code-doc-sync-demo"),
        github_commit_sha=os.getenv("GITHUB_COMMIT_SHA", "a13740a"),
        github_ref=os.getenv("GITHUB_REF", "main"),
        github_test_paths=tuple(
            path.strip()
            for path in os.getenv(
                "GITHUB_TEST_PATHS",
                "src/test/munit/customer-profile-api-test-suite.xml,"
                "src/test/resources/expected-customer-response.json",
            ).split(",")
            if path.strip()
        ),
        atlassian_site_url=os.getenv("ATLASSIAN_SITE_URL", "").rstrip("/"),
        atlassian_email=os.getenv("ATLASSIAN_EMAIL", ""),
        atlassian_api_token=os.getenv("ATLASSIAN_API_TOKEN", ""),
        jira_issue_key=os.getenv("JIRA_ISSUE_KEY", "SCRUM-5"),
        confluence_page_id=os.getenv("CONFLUENCE_PAGE_ID", "425985"),
    )

    required = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "GITHUB_TOKEN": settings.github_token,
        "ATLASSIAN_SITE_URL": settings.atlassian_site_url,
        "ATLASSIAN_EMAIL": settings.atlassian_email,
        "ATLASSIAN_API_TOKEN": settings.atlassian_api_token,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing settings: {', '.join(missing)}")
    return settings

