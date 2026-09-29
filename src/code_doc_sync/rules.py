from code_doc_sync.models import ChangePacket, ConsistencyStatus, RuleFinding


def run_rules(packet: ChangePacket) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    issue_key = packet.issue.identifier.upper()
    commit_text = f"{packet.code_change.commit_message} {packet.code_change.commit_sha}"
    issue_linked = issue_key in commit_text.upper()
    findings.append(
        RuleFinding(
            rule="issue-key-in-commit",
            status=(
                ConsistencyStatus.CONSISTENT
                if issue_linked
                else ConsistencyStatus.INCONSISTENT
            ),
            explanation=(
                f"Commit references {issue_key}."
                if issue_linked
                else f"Commit does not reference {issue_key}."
            ),
        )
    )

    changed_paths = [item.path.lower() for item in packet.code_change.files]
    implementation_changed = any(
        path.endswith((".dwl", ".java", ".py", ".js", ".ts"))
        for path in changed_paths
    )
    tests_changed = any(
        "test" in path or path.endswith((".spec.js", ".spec.ts"))
        for path in changed_paths
    )
    findings.append(
        RuleFinding(
            rule="tests-change-with-implementation",
            status=(
                ConsistencyStatus.CONSISTENT
                if not implementation_changed or tests_changed
                else ConsistencyStatus.INCONSISTENT
            ),
            explanation=(
                "The commit includes a test change."
                if tests_changed
                else "Implementation changed, but the commit contains no test-file change."
            ),
        )
    )

    findings.append(
        RuleFinding(
            rule="required-evidence-present",
            status=(
                ConsistencyStatus.CONSISTENT
                if packet.issue.content
                and packet.design_document.content
                and packet.code_change.files
                else ConsistencyStatus.MISSING_EVIDENCE
            ),
            explanation="Jira, Confluence, and code-change evidence were collected.",
        )
    )
    return findings

