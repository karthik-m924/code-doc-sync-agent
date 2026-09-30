import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from code_doc_sync.connectors.mcp_utils import result_payload
from code_doc_sync.models import ApprovalPlan, ConfluenceSectionUpdate, Evidence


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


class AtlassianWriter:
    def __init__(
        self,
        site_url: str,
        email: str,
        token: str,
        jira_project: str,
        confluence_space: str,
    ) -> None:
        connector = AtlassianConnector(
            site_url, email, token, jira_project, confluence_space
        )
        self._server_env = connector._server_env
        self._jira_project = jira_project
        self._confluence_space = confluence_space

    async def apply(self, plan: ApprovalPlan, plan_id: str) -> dict[str, str]:
        executable = shutil.which("mcp-atlassian")
        if not executable:
            executable = str(Path(sys.executable).with_name("mcp-atlassian.exe"))
        server = StdioServerParameters(
            command=executable,
            args=[
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
                    "jira_get_issue", {"issue_key": plan.jira_issue_key}
                )
                issue = _unwrap_result(result_payload(issue_result))
                current_status = _issue_status(issue)
                target_status = plan.jira_suggestion.suggested_status.strip()
                transition_result = "Already in the suggested status"
                if current_status.casefold() != target_status.casefold():
                    transitions_result = await session.call_tool(
                        "jira_get_transitions", {"issue_key": plan.jira_issue_key}
                    )
                    transitions = _unwrap_result(result_payload(transitions_result))
                    transition_id = _find_transition_id(transitions, target_status)
                    if not transition_id:
                        raise ValueError(
                            f"Jira status '{target_status}' is not an available transition."
                        )
                    result_payload(await session.call_tool(
                        "jira_transition_issue",
                        {
                            "issue_key": plan.jira_issue_key,
                            "transition_id": transition_id,
                        },
                    ))
                    transition_result = f"Moved to {target_status}"

                jira_comment = (
                    f"{plan.jira_suggestion.comment}\n\n"
                    "Acceptance checklist\n"
                    + "\n".join(
                        f"- [ ] {item}"
                        for item in plan.jira_suggestion.acceptance_checklist
                    )
                    + f"\n\nCode-Doc Sync plan: {plan_id}"
                )
                result_payload(await session.call_tool(
                    "jira_add_comment",
                    {"issue_key": plan.jira_issue_key, "body": jira_comment},
                ))

                page_result = await session.call_tool(
                    "confluence_get_page", {"page_id": plan.confluence_page_id}
                )
                page = _unwrap_result(result_payload(page_result))
                title = _first_text(page, "title", "name") or plan.confluence_page_id
                content = _content(_select_page_content(page))
                for update in plan.confluence_suggestion.section_updates:
                    content = apply_section_update(content, update)
                result_payload(await session.call_tool(
                    "confluence_update_page",
                    {
                        "page_id": plan.confluence_page_id,
                        "title": title,
                        "content": content,
                        "content_format": "markdown",
                        "is_minor_edit": False,
                        "version_comment": f"Applied Code-Doc Sync plan {plan_id}",
                    },
                ))
        return {
            "jira": f"Comment added. {transition_result}.",
            "confluence": (
                f"Updated {len(plan.confluence_suggestion.section_updates)} section(s)."
            ),
        }


def apply_section_update(content: str, update: ConfluenceSectionUpdate) -> str:
    body = _strip_outer_fence(update.content)
    heading_pattern = re.compile(
        rf"(?im)^(?P<marks>#{1,6})\s+{re.escape(update.section.strip())}\s*$"
    )
    match = heading_pattern.search(content)
    if not match:
        if update.operation == "remove":
            return content
        return f"{content.rstrip()}\n\n## {update.section.strip()}\n\n{body}\n"

    level = len(match.group("marks"))
    next_heading = re.compile(rf"(?m)^#{{1,{level}}}\s+").search(content, match.end())
    end = next_heading.start() if next_heading else len(content)
    if update.operation == "remove":
        return (content[: match.start()].rstrip() + "\n\n" + content[end:].lstrip())
    if update.operation == "add":
        existing_body = content[match.end() : end].strip()
        replacement = f"{match.group(0)}\n\n{existing_body}\n\n{body}\n\n"
    else:
        replacement = f"{match.group(0)}\n\n{body}\n\n"
    return content[: match.start()] + replacement + content[end:].lstrip()


def _strip_outer_fence(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"`{3,4}(?:\w+)?\s*\n(.*?)\n`{3,4}", value, re.DOTALL)
    return match.group(1).strip() if match else value


def _find_transition_id(payload: Any, target_status: str) -> str:
    if isinstance(payload, dict):
        name = payload.get("name") or payload.get("to", {}).get("name")
        if isinstance(name, str) and name.casefold() == target_status.casefold():
            identifier = payload.get("id") or payload.get("transition_id")
            return str(identifier) if identifier is not None else ""
        for value in payload.values():
            found = _find_transition_id(value, target_status)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _find_transition_id(value, target_status)
            if found:
                return found
    return ""


def _issue_status(payload: Any) -> str:
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, str):
            return status
        if isinstance(status, dict):
            name = status.get("name")
            if isinstance(name, str):
                return name
        for value in payload.values():
            found = _issue_status(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = _issue_status(value)
            if found:
                return found
    return ""


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

