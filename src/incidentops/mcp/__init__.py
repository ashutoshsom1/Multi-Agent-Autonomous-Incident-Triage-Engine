"""Model Context Protocol (MCP) integrations."""

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

__all__ = [
    "mcp__loki_search",
    "mcp__elasticsearch_query",
    "mcp__k8s_get_pod_logs",
    "mcp__prometheus_query",
    "mcp__prometheus_query_range",
    "mcp__github_get_commit",
    "mcp__github_compare_commits",
    "mcp__github_list_pull_requests",
    "mcp__k8s_rollout_undo",
    "mcp__k8s_restart_deployment",
    "mcp__k8s_scale_deployment",
]
