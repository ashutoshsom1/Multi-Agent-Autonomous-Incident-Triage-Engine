"""Codebase Inspection models conforming to Worker Agent 3 output contract."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CodebaseInspectionResult(BaseModel):
    """Release engineering correlation findings extracted from Git commits and PRs."""
    suspect_deployment_found: bool = Field(
        description="Whether a suspect deployment, commit, or PR was correlated with the incident"
    )
    commit_sha: Optional[str] = Field(default=None, description="Suspect Git commit SHA")
    pr_number: Optional[int] = Field(default=None, description="Correlated Pull Request number")
    author: Optional[str] = Field(default=None, description="Author email or GitHub handle")
    deployment_timestamp: Optional[str] = Field(
        default=None,
        description="ISO-8601 UTC timestamp of deployment"
    )
    offending_code_paths: List[str] = Field(
        default_factory=list,
        description="List of file paths and line numbers implicated (e.g. 'src/db/pool.py:L48')"
    )
    diff_analysis: str = Field(
        description="Concise summary of code change introducing the fault"
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
