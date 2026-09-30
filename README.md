# Code-Doc Sync Agent

A GitHub-native pull-request validator that compares a code change with its Jira
requirement, Confluence design, and tests.

## Pull-request flow

1. A developer opens or updates a pull request.
2. GitHub Actions starts the `Code-Doc Sync` check.
3. Read-only connectors collect the PR diff, Jira issue, Confluence page, and
   test artifacts.
4. Deterministic rules and the OpenAI Responses API produce a structured review.
5. The action creates or updates one `Code-Doc Sync Review` comment on the PR.
6. The check fails when the evidence is inconsistent or incomplete.
7. A maintainer can open the linked manual workflow and approve the exact plan.
8. The action updates Jira and named Confluence sections, then records an audit
   result on the PR.

The PR comment includes findings, evidence, recommended actions, a proposed Jira
comment and status, and proposed Confluence documentation changes.

## Phase boundaries

### Review: suggest only

- Jira and Confluence access is read-only.
- The agent publishes suggestions only on the GitHub PR.
- A human decides whether the suggested changes are correct.

### Approval-based updates

The dashboard includes an **Apply recommended changes** control. It opens the
workflow's manual-run page and supplies the pull-request number and plan ID to
enter. The write run validates that the plan is the latest dashboard plan and
that the PR commit has not changed. It also refuses to apply the same plan
twice.

The approved run adds the proposed Jira comment, performs the suggested Jira
transition when available, and updates only the named Confluence sections. It
then posts an audit comment on the PR. New commits make the plan stale and
require a fresh review.

## Demo scenario

- Jira: `SCRUM-5`
- Confluence page: `425985`
- GitHub repository: `karthik-m924/code-doc-sync-demo`
- Expected result: inconsistent

The code adds `preferredLanguage`, while the Confluence design and test artifacts
still describe the previous response contract.

## Architecture

- `action.yml`: reusable composite GitHub Action
- `examples/code-doc-sync.yml`: workflow installed in a target repository
- `src/code_doc_sync/review_pr.py`: PR event orchestrator
- `src/code_doc_sync/connectors`: GitHub and Atlassian MCP connectors
- `src/code_doc_sync/rules.py`: deterministic checks
- `src/code_doc_sync/analyze.py`: OpenAI Structured Outputs analysis
- `src/code_doc_sync/github_review.py`: PR comment renderer and publisher
- `src/code_doc_sync/apply_approval.py`: guarded Jira and Confluence write path

## Repository configuration

Add these GitHub Actions secrets to the target repository:

- `OPENAI_API_KEY`
- `ATLASSIAN_EMAIL`
- `ATLASSIAN_API_TOKEN`

Add these GitHub Actions variables:

- `ATLASSIAN_SITE_URL`
- `CONFLUENCE_PAGE_ID`

Then copy `examples/code-doc-sync.yml` to
`.github/workflows/code-doc-sync.yml` in the target repository.

## Local verification

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
python -m code_doc_sync.review_pr --pr-number 1
```

Omit `--publish` during local verification to avoid changing the PR. The JSON
report and rendered PR comment are written beneath `output/`.

