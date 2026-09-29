import json
from typing import Any

from mcp.types import (
    BlobResourceContents,
    CallToolResult,
    EmbeddedResource,
    TextContent,
    TextResourceContents,
)


def result_payload(result: CallToolResult) -> Any:
    if result.isError:
        raise RuntimeError(result_text(result) or "MCP tool call failed.")
    for block in result.content:
        if not isinstance(block, EmbeddedResource):
            continue
        if isinstance(block.resource, TextResourceContents):
            return block.resource.text
        if isinstance(block.resource, BlobResourceContents):
            return block.resource.blob
    if result.structuredContent:
        return result.structuredContent

    text = result_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def result_text(result: CallToolResult) -> str:
    return "\n".join(
        block.text for block in result.content if isinstance(block, TextContent)
    )

