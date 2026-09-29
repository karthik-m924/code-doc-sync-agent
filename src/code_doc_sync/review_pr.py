import argparse
import asyncio
import json
import os
from pathlib import Path

from code_doc_sync.analyze import analyze_packet
from code_doc_sync.collect import collect_pull_request_packet
from code_doc_sync.config import load_settings
from code_doc_sync.github_review import render_review, upsert_pull_request_comment
from code_doc_sync.models import ConsistencyStatus
from code_doc_sync.rules import run_rules


def _event_pull_number() -> int | None:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        return None
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    number = event.get("pull_request", {}).get("number") or event.get("number")
    return int(number) if number else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review a GitHub pull request against Jira and Confluence."
    )
    parser.add_argument("--pr-number", type=int, default=_event_pull_number())
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--fail-on-inconsistent", action="store_true")
    args = parser.parse_args()
    if args.pr_number is None:
        parser.error("--pr-number is required outside a pull_request workflow.")

    settings = load_settings()
    packet = asyncio.run(collect_pull_request_packet(settings, args.pr_number))
    rule_findings = run_rules(packet)
    report = analyze_packet(
        packet,
        rule_findings,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    markdown = render_review(packet, report)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "pr-comment.md").write_text(
        markdown + "\n", encoding="utf-8"
    )

    if args.publish:
        upsert_pull_request_comment(
            token=settings.github_token,
            owner=settings.github_owner,
            repo=settings.github_repo,
            pull_number=args.pr_number,
            body=markdown,
        )
    print(markdown)

    if (
        args.fail_on_inconsistent
        and report.overall_status != ConsistencyStatus.CONSISTENT
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
