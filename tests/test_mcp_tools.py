"""Unit tests for Model Context Protocol (MCP) tools."""

import pytest
from incidentops.mcp.tools import (
    mcp__loki_search,
    mcp__elasticsearch_query,
    mcp__k8s_get_pod_logs,
    mcp__prometheus_query,
    mcp__prometheus_query_range,
    mcp__github_get_commit,
    mcp__github_compare_commits,
    mcp__github_list_pull_requests,
    mcp__k8s_rollout_undo,
    mcp__k8s_restart_deployment,
    mcp__k8s_scale_deployment,
)


@pytest.mark.asyncio
async def test_mcp_loki_search():
    res = await mcp__loki_search(query='{app="order-service-api"} |= "error"')
    assert res["status"] == "success"
    assert res["source"] == "loki"
    assert "error_rate" in res
    assert len(res["streams"]) > 0


@pytest.mark.asyncio
async def test_mcp_k8s_get_pod_logs():
    res = await mcp__k8s_get_pod_logs(namespace="production", pod_name="order-service-api-123", previous=True)
    assert res["status"] == "success"
    assert "raw_logs" in res
    assert "504 Gateway Timeout" in res["raw_logs"]


@pytest.mark.asyncio
async def test_mcp_prometheus_query_range():
    res = await mcp__prometheus_query_range(
        query="histogram_quantile(0.99, http_duration)",
        start="now-15m",
        end="now"
    )
    assert res["status"] == "success"
    assert res["saturation_detected"] is True
    assert "telemetry_evidence" in res


@pytest.mark.asyncio
async def test_mcp_github_tools():
    prs = await mcp__github_list_pull_requests(repo="acme-corp/order-service-api")
    assert prs["status"] == "success"
    assert len(prs["pull_requests"]) > 0
    assert prs["pull_requests"][0]["number"] == 412

    commit = await mcp__github_get_commit(repo="acme-corp/order-service-api", commit_sha="d4e29ab")
    assert commit["status"] == "success"
    assert len(commit["offending_paths"]) > 0


@pytest.mark.asyncio
async def test_mcp_remediation_tools():
    undo = await mcp__k8s_rollout_undo(namespace="production", deployment="order-service-api")
    assert undo["status"] == "success"
    assert "rolled back successfully" in undo["output"]

    restart = await mcp__k8s_restart_deployment(namespace="production", deployment="payment-gateway")
    assert restart["status"] == "success"

    scale = await mcp__k8s_scale_deployment(namespace="production", deployment="order-service-api", replicas=5)
    assert scale["status"] == "success"
