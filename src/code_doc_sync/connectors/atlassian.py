import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from code_doc_sync.connectors.mcp_utils import result_payload
from code_doc_sync.models import Evidence


class AtlassianConnector:
    def __init__(
        self,
        site_url: str,
        email: str,
        token: str,
        jira_project: str,
        confluence_space: str,
    ) -> None:
        self._site_url = site_url.rstrip("/")
        self._jira_project = jira_project
        self._confluence_space = confluence_space
        self._server_env = os.environ.copy()
        self._server_env.update(
            {
                "JIRA_URL": self._site_url,
                "JIRA_USERNAME": email,
                "JIRA_API_TOKEN": token,
                "CONFLUENCE_URL": f"{self._site_url}/wiki",
                "CONFLUENCE_USERNAME": email,
                "CONFLUENCE_API_TOKEN": token,
            }
        )

    async def collect(
        self, issue_key: str, page_id: str
    ) -> tuple[Evidence, Evidence]:
        executable = shutil.which("mcp-atlassian")
        if not executable:
            executable = str(Path(sys.executable).with_name("mcp-atlassian.exe"))
        server = StdioServerParameters(
            command=executable,
            args=[
                "--read-only",
                "--jira-projects-filter",
                self._jira_project,
                "--confluence-spaces-filter",
                self._confluence_space,
            ],
            env=self._server_env,
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                issue_result = await session.call_tool(
                    "jira_get_issue", {"issue_key": issue_key}
                )
                page_result = await session.call_tool(
                    "confluence_get_page", {"page_id": page_id}
                )

        issue = _unwrap_result(result_payload(issue_result))
        page = _unwrap_result(result_payload(page_result))
        issue_content = _select_issue_content(issue)
        page_content = _select_page_content(page)
        return (
            Evidence(
                source="jira",
                identifier=issue_key,
                title=_first_text(issue, "summary", "title") or issue_key,
                url=f"{self._site_url}/browse/{issue_key}",
                content=_content(issue_content),
            ),
            Evidence(
                source="confluence",
                identifier=page_id,
                title=_first_text(page, "title", "name") or page_id,
                url=f"{self._site_url}/wiki/pages/viewpage.action?pageId={page_id}",
                content=_content(page_content),
            ),
        )


def _first_text(payload: Any, *keys: str) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            found = _first_text(value, *keys)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _first_text(value, *keys)
            if found:
                return found
    return ""


def _unwrap_result(payload: Any) -> Any:
    while isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return payload
    return payload


def _select_issue_content(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    return {
        key: payload[key]
        for key in ("key", "summary", "description", "status", "issue_type", "priority")
        if key in payload
    }


def _select_page_content(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return payload
    content = metadata.get("content", {})
    if isinstance(content, dict):
        return content.get("value", content)
    return content


def _content(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, indent=2, ensure_ascii=True)

