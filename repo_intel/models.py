"""Pydantic v2 schema for the report. Gives validation, typed API responses
and an auto-generated OpenAPI schema. The builder produces plain dicts;
`Report.model_validate(...)` turns them into a validated, typed object.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GitInfo(BaseModel):
    active_branch: str | None = None
    head: str | None = None
    branches: int = 0
    tags: int = 0
    latest_tag: str | None = None


class Summary(BaseModel):
    commits: int
    files: int
    authors: int
    bugfix_commits: int
    total_churn: int
    avg_churn_per_commit: float = 0.0
    first_commit: str | None = None
    last_commit: str | None = None
    health_score: float = Field(ge=0, le=100)
    issue_linked_ratio: float = 0.0
    tracked_bugfixes: int = 0
    complexity_available: bool = False


class Readiness(BaseModel):
    score: float = Field(ge=0, le=100)
    verdict: str
    window_days: int
    commits_in_window: int
    bugfix_rate: float | None = None
    avg_churn: float | None = None
    active_hotspots: int | None = None
    reasons: list[str] = []


class Prediction(BaseModel):
    trend: str
    risk_level: str | None = None
    months_analyzed: int = 0
    bugfix_rate_slope: float | None = None
    churn_slope: float | None = None
    projected_next_month_bugfix_rate: float | None = None
    note: str | None = None


class FileRow(BaseModel):
    path: str
    commits: int
    insertions: int = 0
    deletions: int = 0
    churn: int
    bugfixes: int
    bugfix_ratio: float
    authors: int
    top_author: str
    top_author_share: float = Field(ge=0, le=1)
    bus_factor: int
    risk_score: float = Field(ge=0, le=100)
    recency: float = Field(ge=0, le=1)
    signals: dict[str, float] = {}
    last_seen: str | None = None
    complexity: float | None = None
    complexity_max: int | None = None
    complexity_language: str | None = None


class DepartureRisk(BaseModel):
    author: str
    owned_files: int
    codebase_share: float = Field(ge=0, le=1)
    files: list[str] = []


class ComplexityPoint(BaseModel):
    commit: str
    date: str
    avg_complexity: float
    functions: int
    files: int


class Coupling(BaseModel):
    file_a: str
    file_b: str
    shared_changes: int
    confidence: float = Field(ge=0, le=1)
    cross_module: bool


class Author(BaseModel):
    author: str
    commits: int
    share: float = Field(ge=0, le=1)


class ActivityBucket(BaseModel):
    month: str
    commits: int
    bugfixes: int
    churn: int


class Flag(BaseModel):
    level: str
    code: str
    message: str


class Report(BaseModel):
    """The complete validated report."""

    repo: str
    generated_at: str
    git: GitInfo = GitInfo()
    summary: Summary
    release_readiness: Readiness
    prediction: Prediction
    hotspots: list[FileRow] = []
    knowledge_silos: list[FileRow] = []
    departure_risk: list[DepartureRisk] = []
    coupling: list[Coupling] = []
    authors: list[Author] = []
    commit_activity: list[ActivityBucket] = []
    complexity_trend: list[ComplexityPoint] = []
    flags: list[Flag] = []
    all_files: list[FileRow] = []


class Narrative(BaseModel):
    text: str
    source: str
    model: str | None = None
    error: str | None = None
    cached: bool | None = None
