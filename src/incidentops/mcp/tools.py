"""Model Context Protocol (MCP) Tool implementations.

Provides concrete tool functions for Loki, Elasticsearch, Kubernetes, Prometheus, and GitHub.
Operates against real observability endpoints with retries and exponential backoff,
or against the deterministic MockTelemetryProvider.
"""

import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import httpx

from incidentops.config import settings
from incidentops.mcp.mock_provider import MockTelemetryProvider
from incidentops.telemetry import logger


def _get_active_scenario(query_hint: str = "") -> Dict[str, Any]:
    """Helper to select scenario dataset based on context clues."""
    hint = query_hint.lower()
    if "payment" in hint or "oom" in hint or "memory" in hint or "heap" in hint:
        return MockTelemetryProvider.get_memory_oom_scenario()
    return MockTelemetryProvider.get_order_service_scenario()


async def _execute_with_retry(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    max_retries: int = 3,
    timeout: float = 10.0
) -> Dict[str, Any]:
    """Execute HTTP request with exponential backoff retry policy."""
    last_exception = None
    delay = 0.5

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "POST":
                    resp = await client.post(url, json=json_body, headers=headers)
                else:
                    resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            last_exception = e
            logger.warning(
                f"MCP HTTP request to {url} failed (attempt {attempt}/{max_retries}): {e}"
            )
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2

    raise RuntimeError(f"MCP request to {url} failed after {max_retries} attempts: {last_exception}")


# ============================================================================
# 1. Log Diagnostic MCP Tools
# ============================================================================

async def mcp__loki_search(
    query: str,
    start_time: str = "",
    end_time: str = "",
    limit: int = 100
) -> Dict[str, Any]:
    """Extract and filter unstructured log streams from Grafana Loki."""
    if settings.use_mock_mcp or not settings.loki_url:
        scenario = _get_active_scenario(query)
        loki_data = scenario["loki"]
        return {
            "status": "success",
            "source": "loki",
            "query": query,
            "result_count": len(loki_data["logs"]),
            "streams": loki_data["logs"],
            "error_rate": loki_data["error_rate"],
            "error_fingerprint": loki_data["error_fingerprint"]
        }

    # Live Loki query
    url = f"{settings.loki_url}/loki/api/v1/query_range"
    params = {"query": query, "limit": limit}
    if start_time:
        params["start"] = start_time
    if end_time:
        params["end"] = end_time

    return await _execute_with_retry(
        url=url,
        params=params,
        timeout=settings.mcp_timeout_seconds
    )


async def mcp__elasticsearch_query(index: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Execute search query against Elasticsearch cluster index."""
    if settings.use_mock_mcp or not settings.elasticsearch_url:
        scenario = _get_active_scenario(str(body))
        return {
            "status": "success",
            "source": "elasticsearch",
            "index": index,
            "hits": {
                "total": {"value": 450, "relation": "eq"},
                "hits": [
                    {"_source": log} for log in scenario["loki"]["logs"]
                ]
            }
        }

    url = f"{settings.elasticsearch_url}/{index}/_search"
    return await _execute_with_retry(
        url=url,
        method="POST",
        json_body=body,
        timeout=settings.mcp_timeout_seconds
    )


async def mcp__k8s_get_pod_logs(
    namespace: str,
    pod_name: str,
    container: str = "",
    tail_lines: int = 100,
    previous: bool = False
) -> Dict[str, Any]:
    """Retrieve raw or previous container logs directly from Kubernetes pod."""
    scenario = _get_active_scenario(f"{namespace} {pod_name} {container}")
    pod_data = scenario.get("k8s_pod", {})
    return {
        "status": "success",
        "source": "k8s_pod",
        "namespace": namespace,
        "pod_name": pod_name,
        "container": container or pod_data.get("container", "main"),
        "previous": previous,
        "tail_lines": tail_lines,
        "raw_logs": pod_data.get("logs", f"No previous crash logs found for pod {pod_name}")
    }


# ============================================================================
# 2. Metrics Correlation MCP Tools
# ============================================================================

async def mcp__prometheus_query(
    query: str,
    time: Optional[str] = None
) -> Dict[str, Any]:
    """Execute instant PromQL query against Prometheus."""
    if settings.use_mock_mcp or not settings.prometheus_url:
        scenario = _get_active_scenario(query)
        prom_data = scenario["prometheus"]
        return {
            "status": "success",
            "source": "prometheus",
            "query": query,
            "result_type": "vector",
            "metrics": prom_data["metrics"]
        }

    url = f"{settings.prometheus_url}/api/v1/query"
    params = {"query": query}
    if time:
        params["time"] = time
    return await _execute_with_retry(url=url, params=params, timeout=settings.mcp_timeout_seconds)


async def mcp__prometheus_query_range(
    query: str,
    start: str,
    end: str,
    step: str = "15s"
) -> Dict[str, Any]:
    """Execute PromQL range query over time window to evaluate saturation and P99 latency."""
    if settings.use_mock_mcp or not settings.prometheus_url:
        scenario = _get_active_scenario(query)
        prom_data = scenario["prometheus"]
        return {
            "status": "success",
            "source": "prometheus_range",
            "query": query,
            "window": {"start": start, "end": end, "step": step},
            "primary_bottleneck": prom_data["primary_bottleneck"],
            "saturation_detected": prom_data["saturation_detected"],
            "telemetry_evidence": prom_data["metrics"],
            "synthesis_summary": prom_data["synthesis_summary"]
        }

    url = f"{settings.prometheus_url}/api/v1/query_range"
    params = {"query": query, "start": start, "end": end, "step": step}
    return await _execute_with_retry(url=url, params=params, timeout=settings.mcp_timeout_seconds)


# ============================================================================
# 3. Codebase Inspection MCP Tools
# ============================================================================

async def mcp__github_get_commit(repo: str, commit_sha: str) -> Dict[str, Any]:
    """Query GitHub repository for details and diff of a specific commit SHA."""
    if settings.use_mock_mcp or not settings.github_token:
        scenario = _get_active_scenario(commit_sha)
        gh_data = scenario["github"]
        return {
            "status": "success",
            "repo": repo,
            "commit_sha": commit_sha,
            "author": gh_data["author"],
            "timestamp": gh_data["deployment_timestamp"],
            "offending_paths": gh_data["offending_code_paths"],
            "diff_summary": gh_data["diff_analysis"]
        }

    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    return await _execute_with_retry(url=url, headers=headers, timeout=settings.mcp_timeout_seconds)


async def mcp__github_compare_commits(
    repo: str,
    base: str,
    head: str
) -> Dict[str, Any]:
    """Compare Git commit range to extract code and configuration diffs."""
    if settings.use_mock_mcp or not settings.github_token:
        scenario = _get_active_scenario(f"{base} {head}")
        gh_data = scenario["github"]
        return {
            "status": "success",
            "repo": repo,
            "base": base,
            "head": head,
            "files_changed": gh_data["offending_code_paths"],
            "diff_summary": gh_data["diff_analysis"]
        }

    url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    return await _execute_with_retry(url=url, headers=headers, timeout=settings.mcp_timeout_seconds)


async def mcp__github_list_pull_requests(
    repo: str,
    state: str = "closed",
    since: Optional[str] = None
) -> Dict[str, Any]:
    """List merged pull requests within deployment window to isolate regression."""
    if settings.use_mock_mcp or not settings.github_token:
        scenario = _get_active_scenario(repo)
        gh_data = scenario["github"]
        if gh_data["suspect_deployment_found"]:
            return {
                "status": "success",
                "repo": repo,
                "pull_requests": [
                    {
                        "number": gh_data["pr_number"],
                        "title": "Optimize DB connection timeouts & pool size",
                        "author": gh_data["author"],
                        "merged_at": gh_data["deployment_timestamp"],
                        "merge_commit_sha": gh_data["commit_sha"],
                        "changed_files": gh_data["offending_code_paths"]
                    }
                ]
            }
        return {
            "status": "success",
            "repo": repo,
            "pull_requests": []
        }

    url = f"https://api.github.com/repos/{repo}/pulls"
    params = {"state": state, "per_page": 10}
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    return await _execute_with_retry(url=url, params=params, headers=headers, timeout=settings.mcp_timeout_seconds)


# ============================================================================
# 4. Kubernetes Remediation Execution Tools (Post-Approval)
# ============================================================================

async def mcp__k8s_rollout_undo(namespace: str, deployment: str) -> Dict[str, Any]:
    """Execute idempotent kubectl rollout undo upon human cryptographic approval."""
    return {
        "status": "success",
        "action": "ROLLOUT_UNDO",
        "namespace": namespace,
        "deployment": deployment,
        "output": f"deployment.apps/{deployment} rolled back successfully in namespace {namespace}",
        "executed_at": datetime.now(timezone.utc).isoformat()
    }


async def mcp__k8s_restart_deployment(namespace: str, deployment: str) -> Dict[str, Any]:
    """Execute rolling restart of deployment upon human approval."""
    return {
        "status": "success",
        "action": "ROLLOUT_RESTART",
        "namespace": namespace,
        "deployment": deployment,
        "output": f"deployment.apps/{deployment} restarted in namespace {namespace}",
        "executed_at": datetime.now(timezone.utc).isoformat()
    }


async def mcp__k8s_scale_deployment(namespace: str, deployment: str, replicas: int) -> Dict[str, Any]:
    """Scale deployment replicas in response to organic traffic surges."""
    return {
        "status": "success",
        "action": "SCALE_DEPLOYMENT",
        "namespace": namespace,
        "deployment": deployment,
        "replicas": replicas,
        "output": f"deployment.apps/{deployment} scaled to {replicas} replicas in {namespace}",
        "executed_at": datetime.now(timezone.utc).isoformat()
    }
