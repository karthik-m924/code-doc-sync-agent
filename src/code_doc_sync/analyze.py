import json

from openai import OpenAI

from code_doc_sync.models import AnalysisReport, ChangePacket, RuleFinding


SYSTEM_INSTRUCTIONS = """
You are a read-only software delivery consistency reviewer. Compare the Jira
requirement, Confluence design, GitHub code diff, and test evidence. Report only
claims supported by the supplied Change Packet. Treat deterministic rule results
as evidence, not as infallible conclusions. Mark absent or insufficient material
as missing_evidence. Be concise and provide concrete remediation steps.

Write a proposed Jira comment in clear human language and recommend the Jira
status that should follow from the evidence. Do not claim that Jira was updated.
Write a concise Confluence change summary and a list of exact documentation
changes. Do not claim that Confluence was updated. These are Phase 1 suggestions
that a human will review on the GitHub pull request.
""".strip()


def analyze_packet(
    packet: ChangePacket,
    rule_findings: list[RuleFinding],
    *,
    api_key: str,
    model: str,
) -> AnalysisReport:
    payload = {
        "change_packet": packet.model_dump(mode="json"),
        "deterministic_rule_findings": [
            finding.model_dump(mode="json") for finding in rule_findings
        ],
    }
    response = OpenAI(api_key=api_key).responses.parse(
        model=model,
        reasoning={"effort": "medium"},
        instructions=SYSTEM_INSTRUCTIONS,
        input=json.dumps(payload, indent=2),
        text_format=AnalysisReport,
        store=False,
    )
    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no structured consistency report.")
    return response.output_parsed
