import argparse
import asyncio
import json
from pathlib import Path

from code_doc_sync.analyze import analyze_packet
from code_doc_sync.collect import collect_change_packet
from code_doc_sync.config import load_settings
from code_doc_sync.rules import run_rules


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare a code change with Jira, Confluence, and tests."
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Collect evidence and run deterministic rules without calling OpenAI.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the JSON result to this file in addition to stdout.",
    )
    args = parser.parse_args()

    settings = load_settings()
    packet = asyncio.run(collect_change_packet(settings))
    rules = run_rules(packet)

    if args.collect_only:
        result = {
            "change_packet": packet.model_dump(mode="json"),
            "deterministic_rule_findings": [
                item.model_dump(mode="json") for item in rules
            ],
        }
    else:
        report = analyze_packet(
            packet,
            rules,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        result = report.model_dump(mode="json")

    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
