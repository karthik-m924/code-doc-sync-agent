import argparse
import asyncio

from code_doc_sync.config import load_settings
from code_doc_sync.connectors.atlassian import AtlassianWriter
from code_doc_sync.github_review import (
    APPLIED_MARKER_PREFIX,
    approval_plan_id,
    decode_plan,
    get_pull_request_comment,
    get_pull_request_head_sha,
    has_applied_plan,
    post_pull_request_comment,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a reviewed Code-Doc Sync approval plan."
    )
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--plan-id", required=True)
    args = parser.parse_args()

    settings = load_settings()
    body = get_pull_request_comment(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
        pull_number=args.pr_number,
    )
    plan = decode_plan(body)
    expected_id = approval_plan_id(plan)
    if args.plan_id != expected_id:
        raise SystemExit(
            "Plan ID does not match the latest PR review. Run the workflow with "
            f"plan ID {expected_id}."
        )
    if plan.pull_number != args.pr_number:
        raise SystemExit("The approval plan belongs to a different pull request.")
    current_sha = get_pull_request_head_sha(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
        pull_number=args.pr_number,
    )
    if current_sha != plan.head_sha:
        raise SystemExit(
            "The pull request changed after this plan was generated. Rerun the "
            "Code-Doc Sync review and approve the new plan."
        )
    if has_applied_plan(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
        pull_number=args.pr_number,
        plan_id=expected_id,
    ):
        print(f"Plan {expected_id} was already applied; no changes were made.")
        return

    writer = AtlassianWriter(
        site_url=settings.atlassian_site_url,
        email=settings.atlassian_email,
        token=settings.atlassian_api_token,
        jira_project=plan.jira_issue_key.split("-", 1)[0],
        confluence_space="MAD",
    )
    result = asyncio.run(writer.apply(plan, expected_id))
    audit = "\n".join(
        [
            f"{APPLIED_MARKER_PREFIX}{expected_id} -->",
            "## Code-Doc Sync changes applied",
            "",
            f"**Plan:** `{expected_id}`  ",
            f"**Reviewed commit:** `{plan.head_sha[:12]}`",
            "",
            f"- **Jira {plan.jira_issue_key}:** {result['jira']}",
            f"- **Confluence:** {result['confluence']}",
        ]
    )
    post_pull_request_comment(
        token=settings.github_token,
        owner=settings.github_owner,
        repo=settings.github_repo,
        pull_number=args.pr_number,
        body=audit,
    )
    print(audit)


if __name__ == "__main__":
    main()
