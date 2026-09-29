import asyncio
import os

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def check_mcp() -> None:
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is missing from the local .env file.")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-MCP-Readonly": "true",
        "X-MCP-Toolsets": "repos",
    }

    async with streamablehttp_client(
        "https://api.githubcopilot.com/mcp/", headers=headers
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = {tool.name for tool in listed.tools}

            if "get_commit" not in tools:
                raise SystemExit("The GitHub MCP server did not expose get_commit.")

            commit = await session.call_tool(
                "get_commit",
                {
                    "owner": "karthik-m924",
                    "repo": "code-doc-sync-demo",
                    "sha": "a13740a",
                    "detail": "full_patch",
                },
            )
            if commit.isError:
                raise SystemExit("GitHub MCP could not read commit a13740a.")

            print(f"GitHub MCP exposed {len(tools)} read-only repository tools.")
            print("GitHub MCP commit read succeeded for a13740a.")


def main() -> None:
    asyncio.run(check_mcp())


if __name__ == "__main__":
    main()
