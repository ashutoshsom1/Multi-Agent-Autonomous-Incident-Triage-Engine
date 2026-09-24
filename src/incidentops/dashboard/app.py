"""Streamlit SRE Incident Command Dashboard for IncidentOps AI.

Provides real-time interactive triage simulation, LangGraph telemetry inspection,
Root Cause Analysis (RCA) exploration, and Human-in-the-Loop Slack approval gate.
"""

import asyncio
import json
import streamlit as st

from incidentops.models.alert import AlertPayload
from incidentops.graph.workflow import workflow_manager
from incidentops.config import settings

st.set_page_config(
    page_title="IncidentOps AI | SRE Incident Command",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e2130;
        border: 1px solid #31374f;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-critical {
        background-color: #ff4b4b;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .badge-approved {
        background-color: #00c853;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.sidebar.title("🛡️ IncidentOps AI")
    st.sidebar.caption("Autonomous SRE Multi-Agent Triage Engine")
    st.sidebar.markdown("---")

    st.sidebar.subheader("System Status")
    st.sidebar.markdown(f"**Model:** `{settings.primary_model}`")
    st.sidebar.markdown(f"**Orchestrator:** `LangGraph StateGraph`")
    st.sidebar.markdown(f"**Protocol:** `Model Context Protocol (MCP)`")
    st.sidebar.markdown(f"**Loop Guard:** `<= {settings.max_iteration_guard} iterations`")
    st.sidebar.markdown(f"**Checkpointer:** `Memory / Postgres`")

    st.title("🚨 Multi-Agent Autonomous Incident Triage Engine")
    st.markdown(
        "Autonomous multi-agent triage powered by **Claude 3.5 Sonnet**, **LangGraph**, "
        "and **Model Context Protocol (MCP)** with **Human-in-the-Loop (HITL)** remediation gates."
    )

    # Incident Simulation Selector
    st.subheader("1. Ingest Production Incident Alert")
    col1, col2 = st.columns([3, 1])

    with col1:
        scenario = st.selectbox(
            "Select Incident Scenario to Trigger:",
            [
                "Scenario 1: [P1-CRITICAL] order-service-api Connection Pool Exhaustion (PR #412)",
                "Scenario 2: [P1-CRITICAL] payment-gateway OOMKilled Container CrashLoop (Memory Leak)",
                "Custom JSON Alert Webhook"
            ]
        )

    with col2:
        st.write("")
        st.write("")
        trigger_button = st.button("🚀 Trigger Autonomous Triage", type="primary", use_container_width=True)

    # Session State tracking
    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = None
    if "triage_result" not in st.session_state:
        st.session_state.triage_result = None
    if "remediation_result" not in st.session_state:
        st.session_state.remediation_result = None

    if trigger_button:
        with st.spinner("🤖 Autonomous Multi-Agent Triage in progress (LangGraph StateGraph executing)..."):
            if "Scenario 1" in scenario:
                alert = AlertPayload(
                    alert_id="prom-alert-dbpool-412",
                    service_name="order-service-api",
                    environment="production",
                    severity="CRITICAL",
                    description="HighHttp5xxErrorRate: 450 err/sec on /v2/orders/checkout with connection pool timeout",
                    labels={"namespace": "production", "cluster": "prod-us-east-1", "tier": "backend"}
                )
            elif "Scenario 2" in scenario:
                alert = AlertPayload(
                    alert_id="prom-alert-oom-payment",
                    service_name="payment-gateway",
                    environment="production",
                    severity="CRITICAL",
                    description="PodOOMKilled: JVM heap reached 1.98 GiB / 2.00 GiB cgroup limit (exit code 137)",
                    labels={"namespace": "production", "cluster": "prod-us-east-1", "tier": "payment"}
                )
            else:
                alert = AlertPayload(
                    alert_id="custom-alert-001",
                    service_name="order-service-api",
                    environment="production",
                    severity="HIGH",
                    description="Service latency elevated above SLO threshold",
                    labels={"namespace": "production"}
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(workflow_manager.start_triage(alert))
            loop.close()

            st.session_state.current_thread_id = result["thread_id"]
            st.session_state.triage_result = result
            st.session_state.remediation_result = None

    # Display Triage Results if available
    if st.session_state.triage_result:
        triage_data = st.session_state.triage_result
        state = triage_data.get("state", {})
        thread_id = triage_data.get("thread_id")

        st.markdown("---")
        st.subheader(f"2. Multi-Agent Diagnostic Telemetry [Incident Thread: `{thread_id}`]")

        # 4 Column Layout: Supervisor + 3 Workers
        col_sup, col_log, col_met, col_code = st.columns(4)

        with col_sup:
            st.markdown("### 🎖️ Incident Supervisor")
            sup_plan = state.get("supervisor_plan", {})
            st.caption(f"Loop Iterations: `{state.get('iteration_count')}` / {settings.max_iteration_guard}")
            st.info(f"**Summary:** {sup_plan.get('incident_summary', 'N/A')}")
            st.markdown(f"**Affected Component:** `{sup_plan.get('affected_component', 'N/A')}`")
            st.markdown(f"**Suspected Domains:** {', '.join(sup_plan.get('suspected_fault_domains', []))}")
            st.markdown(f"**Tasks Dispatched:** `{len(sup_plan.get('tasks_to_dispatch', []))}`")

        with col_log:
            st.markdown("### 🔍 Worker 1: Log Diagnostic")
            logs = state.get("log_evidence", {})
            st.caption(f"Source: `{logs.get('log_source', 'loki')}` (Conf: {logs.get('diagnostic_confidence', 0)*100:.0f}%)")
            st.error(f"**Rate:** {logs.get('error_rate_spike', 'N/A')}")
            st.code(logs.get("stack_trace_snippet", "No stack trace"), language="python")
            for finding in logs.get("key_findings", []):
                st.markdown(f"• {finding}")

        with col_met:
            st.markdown("### 📈 Worker 2: Metrics Correlation")
            metrics = state.get("metrics_evidence", {})
            st.caption(f"USEE Method (Conf: {metrics.get('correlation_confidence', 0)*100:.0f}%)")
            st.warning(f"**Bottleneck:** `{metrics.get('primary_bottleneck', 'N/A')}`")
            telem = metrics.get("telemetry_evidence", {})
            if isinstance(telem, dict):
                st.markdown(f"• **Observed:** `{telem.get('observed_value', 'N/A')}`")
                st.markdown(f"• **Threshold:** `{telem.get('threshold_limit', 'N/A')}`")
                st.markdown(f"• **P99 Latency:** `{telem.get('p99_latency_ms', 0)}ms` (Base: `{telem.get('baseline_p99_ms', 0)}ms`)")
            st.caption(metrics.get("synthesis_summary", ""))

        with col_code:
            st.markdown("### 🧬 Worker 3: Codebase Inspector")
            code = state.get("code_evidence", {})
            st.caption(f"Git / PR Triage (Conf: {code.get('confidence_score', 0)*100:.0f}%)")
            if code.get("suspect_deployment_found"):
                st.error(f"**Correlated PR:** `#{code.get('pr_number')}` (SHA: `{code.get('commit_sha')}`)")
                st.markdown(f"**Author:** `{code.get('author')}`")
                st.markdown(f"**Diff Analysis:** {code.get('diff_analysis')}")
                st.markdown(f"**Offending Paths:**")
                for path in code.get("offending_code_paths", []):
                    st.markdown(f"`{path}`")
            else:
                st.success("No recent suspect deployment identified.")

        # Root Cause Analysis & HITL Gate
        st.markdown("---")
        st.subheader("3. Incontrovertible Root Cause Synthesis & Human-in-the-Loop Gate")

        rca_full = state.get("final_rca", {})
        rca = rca_full.get("root_cause_analysis", {})
        remediation = rca_full.get("proposed_remediation", {})
        slack = rca_full.get("slack_block_kit_card", {})

        rca_col, slack_col = st.columns([3, 2])

        with rca_col:
            st.markdown(f"#### 🎯 {rca.get('title', 'Root Cause Analysis')}")
            st.markdown(f"**Confidence:** `{rca.get('confidence_percentage')}%` | **Primary Fault Domain:** `{rca.get('primary_fault_domain')}`")
            st.markdown("**Chronological Chain of Events:**")
            for step in rca.get("chain_of_events", []):
                st.markdown(f"{step}")

            st.markdown("#### ⚡ Proposed Remediation & Blast Radius")
            st.markdown(f"**Action Type:** `{remediation.get('action_type')}`")
            st.code(remediation.get("command_or_script", ""), language="bash")
            st.markdown(f"**Expected Recovery Time (MTTR):** `{remediation.get('expected_recovery_time_seconds')} seconds`")
            st.markdown(f"**Blast Radius Assessment:** {remediation.get('blast_radius')}")
            st.markdown(f"**Rollback Plan:** `{remediation.get('rollback_plan')}`")

        with slack_col:
            st.markdown("#### 💬 Interactive Slack Block Kit Card Preview")
            st.markdown(f"""
            <div style="background-color: #22252a; border-left: 4px solid #e01e5a; padding: 14px; border-radius: 4px;">
                <h4 style="margin: 0; color: #ffffff;">{slack.get('headline', 'Alert Card')}</h4>
                <p style="color: #00c853; font-weight: bold; margin: 4px 0;">🏷️ {slack.get('confidence_badge', '')}</p>
                <p style="color: #cccccc; font-size: 14px; margin: 8px 0;">{slack.get('evidence_summary', '')}</p>
                <div style="margin-top: 10px; font-size: 12px; color: #888888;">
                    HMAC-SHA256 Cryptographic Gate Active
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.write("")
            app_btn_col, rej_btn_col = st.columns(2)
            with app_btn_col:
                approve_clicked = st.button(
                    f"✅ {slack.get('action_button_label', 'Approve Rollback')}",
                    type="primary",
                    use_container_width=True
                )
            with rej_btn_col:
                reject_clicked = st.button(
                    f"❌ {slack.get('reject_button_label', 'Reject & Escalate')}",
                    use_container_width=True
                )

            if approve_clicked:
                with st.spinner("Executing cryptographic authorization & idempotent remediation..."):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(
                        workflow_manager.resume_with_approval(
                            thread_id=thread_id,
                            approved=True,
                            signature="streamlit-operator-hmac-sha256-signature"
                        )
                    )
                    loop.close()
                    st.session_state.remediation_result = res
                    st.rerun()

            if reject_clicked:
                with st.spinner("Escalating to human SRE rotation..."):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(
                        workflow_manager.resume_with_approval(
                            thread_id=thread_id,
                            approved=False,
                            signature="operator-rejected"
                        )
                    )
                    loop.close()
                    st.session_state.remediation_result = res
                    st.rerun()

        # Display Remediation Result
        if st.session_state.remediation_result:
            rem_res = st.session_state.remediation_result
            final_state = rem_res.get("state", {})
            st.markdown("---")
            st.subheader("4. Remediation Execution Log")
            st.success(f"Execution State: `{final_res_status := final_state.get('remediation_status')}`")
            for log in final_state.get("execution_logs", []):
                st.code(log, language="bash")


if __name__ == "__main__":
    main()
