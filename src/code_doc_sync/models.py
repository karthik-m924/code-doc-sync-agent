from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ConsistencyStatus(str, Enum):
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    MISSING_EVIDENCE = "missing_evidence"


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Evidence(BaseModel):
    source: str
    identifier: str
    title: str
    url: str | None = None
    content: str


class ChangedFile(BaseModel):
    path: str
    status: str
    patch: str = ""


class CodeChange(BaseModel):
    repository: str
    commit_sha: str
    commit_message: str
    commit_url: str | None = None
    pull_request_number: int | None = None
    pull_request_title: str | None = None
    pull_request_url: str | None = None
    base_ref: str | None = None
    head_ref: str | None = None
    files: list[ChangedFile] = Field(default_factory=list)


class ChangePacket(BaseModel):
    issue: Evidence
    design_document: Evidence
    code_change: CodeChange
    test_artifacts: list[Evidence] = Field(default_factory=list)


class RuleFinding(BaseModel):
    rule: str
    status: ConsistencyStatus
    explanation: str


class ConsistencyFinding(BaseModel):
    title: str
    severity: Severity
    status: ConsistencyStatus
    explanation: str
    evidence: list[str]
    recommended_action: str


class JiraSuggestion(BaseModel):
    comment: str
    suggested_status: str
    rationale: str
    acceptance_checklist: list[str]


class ConfluenceSectionUpdate(BaseModel):
    section: str
    operation: Literal["add", "replace", "remove"]
    content: str


class ConfluenceSuggestion(BaseModel):
    summary: str
    proposed_changes: list[str]
    section_updates: list[ConfluenceSectionUpdate]


class AreaAssessment(BaseModel):
    status: ConsistencyStatus
    summary: str
    inconsistency: str
    required_update: str


class CodeAssessment(BaseModel):
    status: ConsistencyStatus
    changes: list[str]
    next_step: str


class SyncDashboard(BaseModel):
    code: CodeAssessment
    jira: AreaAssessment
    confluence: AreaAssessment
    tests: AreaAssessment


class AnalysisReport(BaseModel):
    overall_status: ConsistencyStatus
    change_summary: str
    findings: list[ConsistencyFinding]
    recommended_actions: list[str]
    dashboard: SyncDashboard
    jira_suggestion: JiraSuggestion
    confluence_suggestion: ConfluenceSuggestion


class ApprovalPlan(BaseModel):
    version: int = 1
    pull_number: int
    head_sha: str
    jira_issue_key: str
    confluence_page_id: str
    jira_suggestion: JiraSuggestion
    confluence_suggestion: ConfluenceSuggestion
