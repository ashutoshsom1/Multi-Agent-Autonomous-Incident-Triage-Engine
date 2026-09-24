"""Command-line interface (CLI) for IncidentOps AI."""

import argparse
import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from incidentops.config import settings
from incidentops.models.alert import AlertPayload
from incidentops.graph.workflow import workflow_manager

console = Console()


def print_banner():
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                 🚨  INCIDENTOPS AI ENGINE                   ║
    ║   Multi-Agent Autonomous Incident Triage (LangGraph + MCP)  ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold red")


async def run_triage_cli(scenario: str, service: str):
    """Run interactive terminal triage session."""
    print_banner()

    console.print(f"[bold cyan]🔍 Ingesting Alert for Service:[/bold cyan] {service} (Scenario: {scenario})")

    if scenario == "oom":
        alert = AlertPayload(
            alert_id="prom-alert-oom-payment",
            service_name=service or "payment-gateway",
            severity="CRITICAL",
            description="PodOOMKilled: JVM heap reached 1.98 GiB / 2.00 GiB cgroup limit (exit code 137)",
            labels={"namespace": "production", "container": service or "payment-gateway"}
        )
    else:
        alert = AlertPayload(
            alert_id="prom-alert-dbpool-412",
            service_name=service or "order-service-api",
            severity="CRITICAL",
            description="HighHttp5xxErrorRate: 450 err/sec on /v2/orders/checkout with connection pool timeout",
            labels={"namespace": "production", "container": service or "order-api"}
        )

    with console.status("[bold green]Executing LangGraph multi-agent diagnostic triage..."):
        result = await workflow_manager.start_triage(alert)

    thread_id = result["thread_id"]
    state = result["state"]

    console.print(f"\n[bold green]✅ Triage Halted at Human Approval Gate[/bold green] [Thread ID: [bold]{thread_id}[/bold]]\n")

    # Supervisor Summary
    sup_plan = state.get("supervisor_plan", {})
    console.print(Panel(
        f"[bold]Incident Summary:[/bold] {sup_plan.get('incident_summary')}\n"
        f"[bold]Affected Component:[/bold] {sup_plan.get('affected_component')}\n"
        f"[bold]Suspected Fault Domains:[/bold] {', '.join(sup_plan.get('suspected_fault_domains', []))}\n"
        f"[bold]Loop Count:[/bold] {state.get('iteration_count')} / {settings.max_iteration_guard}",
        title="🎖️ Incident Supervisor Plan",
        border_style="cyan"
    ))

    # Diagnostic Telemetry Table
    table = Table(title="📊 Multi-Modal Diagnostic Telemetry Evidence")
    table.add_column("Worker Node", style="bold magenta")
    table.add_column("Source", style="cyan")
    table.add_column("Primary Findings & Bottlenecks", style="white")

    log_data = state.get("log_evidence", {})
    table.add_row(
        "Log Diagnostic",
        log_data.get("log_source", "loki"),
        f"[bold red]{log_data.get('error_fingerprint')}[/bold red]\nVelocity: {log_data.get('error_rate_spike')}"
    )

    metrics_data = state.get("metrics_evidence", {})
    table.add_row(
        "Metrics Correlation",
        "Prometheus",
        f"[bold yellow]{metrics_data.get('primary_bottleneck')}[/bold yellow]\n{metrics_data.get('synthesis_summary')}"
    )

    code_data = state.get("code_evidence", {})
    table.add_row(
        "Codebase Inspector",
        "GitHub",
        f"[bold red]PR #{code_data.get('pr_number')}[/bold red] by {code_data.get('author')}\n{code_data.get('diff_analysis')}"
    )

    console.print(table)

    # Root Cause Synthesis
    rca = state.get("final_rca", {}).get("root_cause_analysis", {})
    rem = state.get("final_rca", {}).get("proposed_remediation", {})

    chain_text = "\n".join([f"  {step}" for step in rca.get("chain_of_events", [])])

    console.print(Panel(
        f"[bold white]{rca.get('title')}[/bold white]\n\n"
        f"[bold cyan]Confidence:[/bold cyan] {rca.get('confidence_percentage')}%  |  "
        f"[bold cyan]Domain:[/bold cyan] {rca.get('primary_fault_domain')}\n\n"
        f"[bold]Causal Chain of Events:[/bold]\n{chain_text}\n\n"
        f"[bold yellow]Proposed Remediation:[/bold yellow] [{rem.get('action_type')}]\n"
        f"[bold green]Command:[/bold green] {rem.get('command_or_script')}\n"
        f"[bold]MTTR Target:[/bold] {rem.get('expected_recovery_time_seconds')}s\n"
        f"[bold]Blast Radius:[/bold] {rem.get('blast_radius')}",
        title="🎯 Incontrovertible Root Cause Diagnostic & Proposed Remediation",
        border_style="red"
    ))

    # Interactive CLI Prompt
    console.print("\n[bold yellow]Interactive Human-in-the-Loop Gate:[/bold yellow]")
    choice = input("Authorize automated remediation action? (y/n): ").strip().lower()

    is_approved = choice in ("y", "yes")
    with console.status("[bold green]Submitting cryptographic authorization to LangGraph..."):
        res = await workflow_manager.resume_with_approval(
            thread_id=thread_id,
            approved=is_approved,
            signature="cli-operator-authorized-key-001"
        )

    final_state = res.get("state", {})
    status = final_state.get("remediation_status")
    console.print(f"\n[bold green]Final Status:[/bold green] {status}")
    for line in final_state.get("execution_logs", []):
        console.print(f"  ⚡ {line}", style="bold white")


def main():
    parser = argparse.ArgumentParser(description="IncidentOps AI Command Line Interface")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Triage command
    triage_parser = subparsers.add_parser("triage", help="Run interactive incident triage")
    triage_parser.add_argument("--scenario", choices=["db_pool", "oom"], default="db_pool", help="Incident scenario")
    triage_parser.add_argument("--service", default="order-service-api", help="Target service name")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Run FastAPI webhook server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port")

    # Dashboard command
    dash_parser = subparsers.add_parser("dashboard", help="Run Streamlit SRE dashboard")
    dash_parser.add_argument("--port", type=int, default=8501, help="Dashboard port")

    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run("incidentops.api.app:app", host=args.host, port=args.port, reload=True)
    elif args.command == "dashboard":
        import subprocess
        subprocess.run(["streamlit", "run", "src/incidentops/dashboard/app.py", "--server.port", str(args.port)])
    elif args.command == "triage":
        asyncio.run(run_triage_cli(scenario=args.scenario, service=args.service))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
