import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check_mcp() -> None:
    load_dotenv()
    site_url = os.getenv("ATLASSIAN_SITE_URL", "").rstrip("/")
    email = os.getenv("ATLASSIAN_EMAIL", "")
    token = os.getenv("ATLASSIAN_API_TOKEN", "")

    if not all((site_url, email, token)):
        raise SystemExit("Atlassian settings are missing from the local .env file.")

    server_env = os.environ.copy()
    server_env.update(
        {
            "JIRA_URL": site_url,
            "JIRA_USERNAME": email,
            "JIRA_API_TOKEN": token,
            "CONFLUENCE_URL": f"{site_url}/wiki",
            "CONFLUENCE_USERNAME": email,
            "CONFLUENCE_API_TOKEN": token,
        }
    )

    executable = Path(sys.executable).with_name("mcp-atlassian.exe")
    server = StdioServerParameters(
        command=str(executable),
        args=[
            "--read-only",
            "--jira-projects-filter",
            "SCRUM",
            "--confluence-spaces-filter",
            "MAD",
        ],
        env=server_env,
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = {tool.name for tool in listed.tools}

            required = {"jira_get_issue", "confluence_get_page"}
            missing = sorted(required - tools)
            if missing:
                raise SystemExit(f"Required MCP tools are missing: {', '.join(missing)}")

            issue = await session.call_tool(
                "jira_get_issue", {"issue_key": "SCRUM-5"}
            )
            page = await session.call_tool(
                "confluence_get_page", {"page_id": "425985"}
            )

            if issue.isError:
                raise SystemExit("MCP Jira read failed.")
            if page.isError:
                raise SystemExit("MCP Confluence read failed.")

            print(f"MCP server exposed {len(tools)} read-only tools.")
            print("MCP Jira read succeeded for SCRUM-5.")
            print("MCP Confluence read succeeded for page 425985.")


def main() -> None:
    asyncio.run(check_mcp())


if __name__ == "__main__":
    main()
