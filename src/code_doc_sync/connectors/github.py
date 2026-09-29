from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from code_doc_sync.connectors.mcp_utils import result_payload
from code_doc_sync.models import ChangedFile, CodeChange, Evidence


class GitHubConnector:
    def __init__(self, token: str, owner: str, repo: str) -> None:
        self._owner = owner
        self._repo = repo
        self._headers = {
            "Authorization": f"Bearer {token}",
            "X-MCP-Readonly": "true",
            "X-MCP-Toolsets": "repos,pull_requests",
        }

    async def collect_pull_request(
        self, pull_number: int, test_paths: tuple[str, ...]
    ) -> tuple[CodeChange, list[Evidence]]:
        async with streamablehttp_client(
            "https://api.githubcopilot.com/mcp/", headers=self._headers
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                base_args = {
                    "owner": self._owner,
                    "repo": self._repo,
                    "pullNumber": pull_number,
                }
                detail_result = await session.call_tool(
                    "pull_request_read", {**base_args, "method": "get"}
                )
                files_result = await session.call_tool(
                    "pull_request_read",
                    {**base_args, "method": "get_files", "perPage": 100},
                )
                detail = _unwrap_json_result(result_payload(detail_result))
                files_payload = _unwrap_json_result(result_payload(files_result))
                files = _find_files(files_payload)
                head = detail.get("head", {})
                base = detail.get("base", {})
                head_sha = head.get("sha") or detail.get("head_sha", "")
                head_ref = head.get("ref") or detail.get("head_ref")
                base_ref = base.get("ref") or detail.get("base_ref")
                change = CodeChange(
                    repository=f"{self._owner}/{self._repo}",
                    commit_sha=head_sha,
                    commit_message=detail.get("title", ""),
                    commit_url=(
                        f"https://github.com/{self._owner}/{self._repo}/commit/{head_sha}"
                        if head_sha
                        else None
                    ),
                    pull_request_number=pull_number,
                    pull_request_title=detail.get("title", ""),
                    pull_request_url=(
                        detail.get("html_url")
                        or f"https://github.com/{self._owner}/{self._repo}/pull/{pull_number}"
                    ),
                    base_ref=base_ref,
                    head_ref=head_ref,
                    files=[
                        ChangedFile(
                            path=item.get("filename") or item.get("path", ""),
                            status=item.get("status", "modified"),
                            patch=item.get("patch", ""),
                        )
                        for item in files
                    ],
                )
                tests = await self._collect_test_artifacts(
                    session,
                    test_paths,
                    f"refs/pull/{pull_number}/head",
                    head_sha or f"refs/pull/{pull_number}/head",
                )
                return change, tests

    async def collect(
        self, commit_sha: str, ref: str, test_paths: tuple[str, ...]
    ) -> tuple[CodeChange, list[Evidence]]:
        async with streamablehttp_client(
            "https://api.githubcopilot.com/mcp/", headers=self._headers
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                commit_result = await session.call_tool(
                    "get_commit",
                    {
                        "owner": self._owner,
                        "repo": self._repo,
                        "sha": commit_sha,
                        "detail": "full_patch",
                    },
                )
                commit = _unwrap(result_payload(commit_result))
                change = _to_code_change(commit, self._owner, self._repo)
                tests = await self._collect_test_artifacts(
                    session, test_paths, ref, commit_sha
                )
                return change, tests

    async def _collect_test_artifacts(
        self,
        session: ClientSession,
        test_paths: tuple[str, ...],
        ref: str,
        display_ref: str,
    ) -> list[Evidence]:
        artifacts: list[Evidence] = []
        for path in test_paths:
            file_result = await session.call_tool(
                "get_file_contents",
                {
                    "owner": self._owner,
                    "repo": self._repo,
                    "path": path,
                    "ref": ref,
                },
            )
            artifacts.append(
                Evidence(
                    source="github",
                    identifier=path,
                    title=path,
                    url=(
                        f"https://github.com/{self._owner}/{self._repo}/blob/"
                        f"{display_ref}/{path}"
                    ),
                    content=_extract_file_content(result_payload(file_result)),
                )
            )
        return artifacts


def _unwrap(payload: Any) -> dict[str, Any]:
    payload = _unwrap_json_result(payload)
    if isinstance(payload, dict):
        for key in ("commit", "data", "result"):
            value = payload.get(key)
            if isinstance(value, dict) and ("sha" in value or "files" in value):
                return value
        return payload
    raise TypeError("GitHub MCP returned an unexpected commit payload.")


def _unwrap_json_result(payload: Any) -> Any:
    while isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
        if isinstance(payload, str):
            import json

            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return payload
    return payload


def _find_files(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("files", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise TypeError("GitHub MCP returned an unexpected pull-request files payload.")


def _to_code_change(
    commit: dict[str, Any], owner: str, repo: str
) -> CodeChange:
    details = commit.get("commit", {})
    message = details.get("message") or commit.get("message", "")
    files = commit.get("files") or []
    return CodeChange(
        repository=f"{owner}/{repo}",
        commit_sha=commit.get("sha", ""),
        commit_message=message,
        commit_url=commit.get("html_url") or commit.get("url"),
        files=[
            ChangedFile(
                path=item.get("filename") or item.get("path", ""),
                status=item.get("status", "modified"),
                patch=item.get("patch", ""),
            )
            for item in files
        ],
    )


def _extract_file_content(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("content", "text", "data"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                nested = _extract_file_content(value)
                if nested:
                    return nested
    return str(payload)
