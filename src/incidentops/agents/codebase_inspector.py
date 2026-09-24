"""Worker Agent 3: Codebase Inspection Agent Node.

Release engineering & PR diff correlation via GitHub MCP tools.
"""

import json
from typing import Any, Dict
from incidentops.models.state import IncidentState
from incidentops.models.code import CodebaseInspectionResult
from incidentops.prompts.codebase_inspector_prompt import CODEBASE_INSPECTOR_AGENT_PROMPT
from incidentops.mcp.tools import mcp__github_list_pull_requests, mcp__github_get_commit
from incidentops.agents.llm_factory import llm_engine


async def codebase_inspector_node(state: IncidentState) -> Dict[str, Any]:
    """Execute codebase inspection worker to correlate Git commits and PR diffs."""
    alert_raw = state.get("alert_raw", {})
    service_name = alert_raw.get("service_name", "unknown-service")
    repo_name = f"acme-corp/{service_name}"

    # 1. MCP Tool Execution (GitHub pull requests & commit diffs)
    prs_result = await mcp__github_list_pull_requests(
        repo=repo_name,
        state="closed"
    )
    commit_result = await mcp__github_get_commit(
        repo=repo_name,
        commit_sha="d4e29ab"
    )

    # 2. Formulate LLM message with tool output
    user_prompt = f"""Repository: {repo_name}
Target Service: {service_name}
Alert Context: {json.dumps(alert_raw, indent=2)}

GitHub MCP Tool Output:
--- Recent Pull Requests ---
{json.dumps(prs_result, indent=2)}

--- Suspect Commit Details ---
{json.dumps(commit_result, indent=2)}

Correlate recent deployments with incident timestamp [T-2h, T].
Analyze diffs for database timeouts, pool reductions, or configuration alterations."""

    # 3. Deterministic Mock Fallback
    mock_result = {
        "suspect_deployment_found": True,
        "commit_sha": "d4e29ab",
        "pr_number": 412,
        "author": "sarah.chen@company.com",
        "deployment_timestamp": "2026-09-24T14:15:00Z",
        "offending_code_paths": [
            "src/database/connection_pool.py:L48",
            "helm/values-prod.yaml:L112"
        ],
        "diff_analysis": (
            "PR #412 ('Optimize DB connection timeouts') reduced pool timeout from 30s to 2s "
            "and max_overflow from 50 to 5 in helm/values-prod.yaml, starving worker threads during traffic burst."
        ),
        "confidence_score": 0.96
    }

    # 4. Invoke LLM Engine
    code_result = await llm_engine.generate_structured(
        system_prompt=CODEBASE_INSPECTOR_AGENT_PROMPT,
        user_message=user_prompt,
        response_model=CodebaseInspectionResult,
        mock_fallback=mock_result
    )

    return {"code_evidence": code_result.model_dump()}
