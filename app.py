from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from recruitflow.ai.feedback_parser import parse_feedback
from recruitflow.ai.resume_parser import parse_resume_with_jd
from recruitflow.core import database as db
from recruitflow.core.state_machine import ALLOWED_TRANSITIONS
from recruitflow.core.workflow import confirm_feedback, confirm_resume_intake
from recruitflow.integrations.wecom import WeComAdapter, build_payload
from recruitflow.utils.files import extract_text

load_dotenv()

DB_PATH = os.getenv("DATABASE_URL", "data/recruitflow.db")

PAGE_INTAKE = "AI候选人录入"
PAGE_FEEDBACK = "面试官反馈"
PAGE_CANDIDATES = "候选人台账"
PAGE_DASHBOARD = "招聘看板"
PAGE_WECOM = "企业微信群"
PAGE_EVENTS = "事件日志"
PAGE_SETTINGS = "岗位配置"

PAGES = [
    PAGE_INTAKE,
    PAGE_FEEDBACK,
    PAGE_CANDIDATES,
    PAGE_DASHBOARD,
    PAGE_WECOM,
    PAGE_EVENTS,
    PAGE_SETTINGS,
]

STAGE_ORDER = list(ALLOWED_TRANSITIONS.keys())
ACTIVE_STAGES = ["待二审", "初试待安排", "初试待反馈", "复试待安排", "复试待反馈", "终试待安排", "Offer审批", "Offer已发", "待入职"]
TERMINAL_STAGES = ["已入职", "不合适", "候选人放弃"]

DEMO_RESUME = """姓名：李明
电话：13800138000
邮箱：liming@example.com
本科，4年B端产品经验，熟悉SaaS、AI Agent、数据分析和SQL。
最近负责招聘运营自动化项目，完成候选人台账、流程看板和消息通知设计。
期望薪资：20-25K，已离职，可两周内到岗。
"""

DEMO_FEEDBACK = "李明可以约面，建议安排下周二下午，重点考察项目推进能力。"

st.set_page_config(
    page_title="RecruitFlow AI",
    page_icon="RF",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    db.init_db(DB_PATH)
    ensure_demo_job()
    inject_css()
    render_sidebar()

    page = st.session_state.get("page", PAGE_INTAKE)
    if page == PAGE_INTAKE:
        render_intake()
    elif page == PAGE_FEEDBACK:
        render_feedback()
    elif page == PAGE_CANDIDATES:
        render_candidates()
    elif page == PAGE_DASHBOARD:
        render_dashboard()
    elif page == PAGE_WECOM:
        render_wecom()
    elif page == PAGE_EVENTS:
        render_events()
    else:
        render_settings()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --rf-border: rgba(15, 23, 42, 0.10);
            --rf-muted: #64748b;
            --rf-ink: #0f172a;
            --rf-panel: #ffffff;
            --rf-soft: #f8fafc;
            --rf-brand: #2563eb;
            --rf-green: #059669;
            --rf-amber: #d97706;
            --rf-red: #dc2626;
        }
        .main .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2.5rem;
            max-width: 1280px;
        }
        [data-testid="stSidebar"] {
            border-right: 1px solid var(--rf-border);
        }
        [data-testid="stMetric"] {
            background: var(--rf-panel);
            border: 1px solid var(--rf-border);
            border-radius: 8px;
            padding: 14px 14px 12px;
        }
        .rf-hero {
            border: 1px solid #0f172a;
            border-radius: 8px;
            background: #0f172a;
            padding: 20px 22px;
            margin-bottom: 18px;
        }
        .rf-eyebrow {
            color: #93c5fd;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .06em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .rf-title {
            color: #ffffff;
            font-size: 28px;
            font-weight: 760;
            line-height: 1.18;
            margin: 0;
        }
        .rf-subtitle {
            color: #cbd5e1;
            font-size: 14px;
            line-height: 1.6;
            margin-top: 6px;
            max-width: 760px;
        }
        .rf-card {
            border: 1px solid var(--rf-border);
            border-radius: 8px;
            background: var(--rf-panel);
            padding: 16px;
            margin-bottom: 14px;
        }
        .rf-section-title {
            color: #0f172a;
            font-size: 18px;
            font-weight: 800;
            margin: 0 0 8px;
        }
        .rf-section-copy {
            color: #475569;
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 12px;
        }
        .rf-note {
            border: 1px solid rgba(37, 99, 235, .18);
            border-radius: 8px;
            background: #eff6ff;
            color: #1e3a8a;
            padding: 10px 12px;
            font-size: 13px;
            line-height: 1.5;
        }
        .rf-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 12px;
            font-weight: 700;
            background: var(--rf-soft);
            color: #334155;
            border: 1px solid var(--rf-border);
            margin-right: 6px;
            margin-bottom: 6px;
        }
        .rf-pill-blue { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
        .rf-pill-green { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
        .rf-pill-amber { background: #fffbeb; color: #b45309; border-color: #fde68a; }
        .rf-pill-red { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
        .rf-divider {
            height: 1px;
            background: var(--rf-border);
            margin: 12px 0;
        }
        .rf-status-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-bottom: 14px;
        }
        .rf-status {
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 12px;
        }
        .rf-status-label {
            color: #64748b;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .rf-status-value {
            color: #0f172a;
            font-size: 16px;
            font-weight: 800;
            overflow-wrap: anywhere;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    st.sidebar.title("RecruitFlow AI")
    st.sidebar.caption("轻量招聘运营 Demo · Streamlit + SQLite")
    st.sidebar.radio("模块", PAGES, key="page")
    st.sidebar.divider()

    st.sidebar.markdown("**演示导览**")
    st.sidebar.caption("建议顺序：录入候选人 → 解析反馈 → 查看台账 → 看板复盘 → 事件日志。")
    if st.sidebar.button("导入演示候选人", use_container_width=True):
        seed_demo_candidate()
        st.sidebar.success("演示候选人已写入/更新")

    st.sidebar.divider()
    st.sidebar.markdown("**当前模式**")
    st.sidebar.code(
        f"AI_PROVIDER={os.getenv('AI_PROVIDER', 'mock')}\n"
        f"TENCENT_DOCS_MODE={os.getenv('TENCENT_DOCS_MODE', 'mock')}\n"
        f"WECOM_NOTIFY_ENABLED={current_wecom_enabled()}"
    )
    st.sidebar.caption("默认 mock 能力可完成现场演示，不依赖外部模型或企业微信授权。")


def render_page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="rf-hero">
            <div class="rf-eyebrow">{eyebrow}</div>
            <h1 class="rf-title">{title}</h1>
            <div class="rf-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_intake() -> None:
    render_page_header(
        "RecruitFlow Intake",
        "AI候选人录入",
        "上传或粘贴简历，选择岗位后生成结构化候选人信息、匹配分析和标准化推荐语。",
    )

    jobs = db.list_jobs(DB_PATH)
    if jobs.empty:
        st.warning("请先在岗位配置中创建岗位。")
        return

    left, right = st.columns([0.42, 0.58], gap="large")
    with left:
        st.markdown('<div class="rf-card">', unsafe_allow_html=True)
        job_options = {f"{row.title} · {row.owner or '未分配'}": int(row.id) for row in jobs.itertuples()}
        selected_label = st.selectbox("目标岗位", list(job_options.keys()))
        job_id = job_options[selected_label]
        job = jobs[jobs["id"] == job_id].iloc[0]
        uploaded = st.file_uploader("上传简历", type=["pdf", "docx", "txt"])
        resume_text = st.text_area("或直接粘贴简历文本", DEMO_RESUME, height=260)
        owner = st.text_input("招聘负责人", value=str(job.get("owner") or "王芳"))
        parse_clicked = st.button("AI解析并生成推荐语", type="primary", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        if uploaded:
            resume_text = extract_text(uploaded.name, uploaded.getvalue())
        if parse_clicked:
            st.session_state["intake_raw_resume"] = resume_text
            st.session_state["intake_result"] = parse_resume_with_jd(resume_text, str(job["title"]), str(job["jd"]))
            st.session_state["intake_job_id"] = job_id
            st.session_state["intake_owner"] = owner

        result = st.session_state.get("intake_result")
        if not result:
            st.info("点击左侧按钮后，这里会展示 AI 结构化结果。")
            st.markdown(
                '<div class="rf-note">Demo 提示：默认简历会匹配“AI产品经理”岗位，可直接点击解析并确认入库。</div>',
                unsafe_allow_html=True,
            )
            return

        st.subheader("AI解析结果")
        c1, c2, c3 = st.columns(3)
        c1.metric("候选人", result.candidate.name)
        c2.metric("匹配分", result.match.score)
        c3.metric("建议", result.match.recommendation_level)

        with st.expander("结构化候选人信息", expanded=True):
            st.json(result.candidate.model_dump())
        with st.expander("匹配点与风险点", expanded=True):
            st.markdown("**匹配点**")
            render_pills(result.match.matched_points or ["待确认"], "green")
            st.markdown("**风险点**")
            render_pills(result.match.risk_points or ["暂无明显风险"], "amber")
        st.text_area("标准化推荐语", result.match.recommendation_text, height=150)

        if st.button("确认入库并推送面试官群", type="primary", use_container_width=True):
            apply_wecom_session_env()
            output = confirm_resume_intake(
                int(st.session_state["intake_job_id"]),
                result,
                st.session_state.get("intake_raw_resume", ""),
                owner=st.session_state.get("intake_owner"),
            )
            st.success(f"已创建/更新候选人并写入事件日志：Application #{output['application_id']}")
            st.session_state.pop("intake_result", None)


def render_feedback() -> None:
    render_page_header(
        "Feedback Inbox",
        "面试官反馈",
        "粘贴面试官反馈，AI识别动作意图，HR确认后更新候选人流程状态。",
    )

    apps = db.applications_view(DB_PATH)
    if apps.empty:
        st.info("暂无候选人，请先完成一次 AI 候选人录入，或从侧边栏导入演示候选人。")
        return

    left, right = st.columns([0.44, 0.56], gap="large")
    with left:
        options = {
            f"#{row.application_id} {row.name} · {row.job_title} · {row.stage}": int(row.application_id)
            for row in apps.itertuples()
        }
        selected = st.selectbox("选择候选申请", list(options.keys()))
        app_id = options[selected]
        current = apps[apps["application_id"] == app_id].iloc[0]
        st.markdown(
            f"""
            <div class="rf-card">
                <span class="rf-pill rf-pill-blue">{current['stage']}</span>
                <span class="rf-pill">{current['owner'] or '未分配'}</span>
                <div class="rf-divider"></div>
                <strong>{current['name']}</strong><br/>
                <span style="color:#64748b;font-size:13px;">{current['job_title']} · 匹配分 {current['score'] or '待确认'}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        raw = st.text_area("粘贴面试官反馈", DEMO_FEEDBACK, height=180)
        if st.button("AI解析反馈", type="primary", use_container_width=True):
            st.session_state["feedback_result"] = parse_feedback(raw)
            st.session_state["feedback_raw"] = raw
            st.session_state["feedback_app_id"] = app_id
            st.session_state["feedback_stage"] = str(current["stage"])

    with right:
        result = st.session_state.get("feedback_result")
        if not result:
            st.info("解析结果会在这里展示，包括动作意图、下一状态、置信度和邀约话术。")
            return

        st.subheader("反馈解析结果")
        c1, c2, c3 = st.columns(3)
        c1.metric("动作意图", result.intent)
        c2.metric("下一状态", result.next_stage or "待确认")
        c3.metric("置信度", f"{result.confidence:.0%}")
        st.json(result.model_dump())
        if result.invitation_message:
            st.text_area("候选人邀约话术", result.invitation_message, height=120)
        if st.button("确认更新流程状态", type="primary", use_container_width=True):
            output = confirm_feedback(
                int(st.session_state["feedback_app_id"]),
                st.session_state["feedback_stage"],  # type: ignore[arg-type]
                result,
                st.session_state["feedback_raw"],
            )
            if output["status"] == "blocked":
                st.warning(output["message"])
            else:
                st.success(f"状态已更新：{output['old_stage']} → {output['new_stage']}")
            st.session_state.pop("feedback_result", None)


def render_candidates() -> None:
    render_page_header(
        "Candidate Ledger",
        "候选人台账",
        "面向 Demo 的可筛选候选人清单，支持按阶段、岗位、负责人、分数和关键词快速定位。",
    )

    data = prepare_applications(db.applications_view(DB_PATH))
    if data.empty:
        st.info("暂无候选人。可先从侧边栏导入演示候选人。")
        return

    filtered = render_candidate_filters(data)
    render_candidate_summary(filtered, data)

    columns = [
        "application_id",
        "name",
        "job_title",
        "stage",
        "score",
        "recommendation_level",
        "owner",
        "education",
        "school",
        "experience_years",
        "expected_salary",
        "updated_at",
    ]
    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "application_id": st.column_config.NumberColumn("申请ID", format="#%d"),
            "name": "候选人",
            "job_title": "岗位",
            "stage": "阶段",
            "score": st.column_config.ProgressColumn("匹配分", min_value=0, max_value=100, format="%d"),
            "recommendation_level": "AI建议",
            "owner": "负责人",
            "education": "学历",
            "school": "学校",
            "experience_years": st.column_config.NumberColumn("年限", format="%.1f"),
            "expected_salary": "期望薪资",
            "updated_at": st.column_config.DatetimeColumn("更新时间", format="YYYY-MM-DD HH:mm"),
        },
    )
    st.download_button(
        "导出台账 CSV",
        filtered[columns].to_csv(index=False).encode("utf-8-sig"),
        file_name="recruitflow_candidates.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_dashboard() -> None:
    render_page_header(
        "Recruiting Dashboard",
        "招聘看板",
        "聚合候选人漏斗、岗位分布、负责人负载和近期推进情况，适合 3 分钟答辩演示。",
    )

    data = prepare_applications(db.applications_view(DB_PATH))
    if data.empty:
        st.info("暂无数据。可先从侧边栏导入演示候选人，或完成一次 AI 候选人录入。")
        return

    filtered = render_dashboard_filters(data)
    render_dashboard_kpis(filtered)

    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        stage_counts = stage_count_frame(filtered)
        fig = px.bar(
            stage_counts,
            x="stage",
            y="count",
            text="count",
            title="招聘阶段漏斗",
            color="stage_group",
            color_discrete_map={"活跃": "#2563eb", "Offer/入职": "#059669", "终态": "#64748b"},
        )
        fig.update_layout(showlegend=False, height=390, margin=dict(l=10, r=10, t=50, b=10))
        fig.update_traces(textposition="outside", cliponaxis=False)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        job_counts = filtered.groupby("job_title", dropna=False).size().reset_index(name="count")
        fig = px.pie(
            job_counts,
            names="job_title",
            values="count",
            title="岗位候选人分布",
            hole=0.48,
            color_discrete_sequence=["#2563eb", "#059669", "#d97706", "#7c3aed", "#475569"],
        )
        fig.update_layout(height=390, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns([0.5, 0.5], gap="large")
    with c1:
        owner_load = filtered.groupby("owner_display", dropna=False).agg(
            candidates=("application_id", "count"),
            avg_score=("score", "mean"),
        ).reset_index().sort_values(["candidates", "avg_score"], ascending=[False, False])
        st.subheader("负责人负载")
        st.dataframe(
            owner_load,
            use_container_width=True,
            hide_index=True,
            column_config={
                "owner_display": "负责人",
                "candidates": "候选人数",
                "avg_score": st.column_config.NumberColumn("平均匹配分", format="%.1f"),
            },
        )
    with c2:
        st.subheader("最近推进")
        recent = filtered.sort_values("updated_at", ascending=False).head(6)
        for row in recent.itertuples():
            st.markdown(
                f"""
                <div class="rf-card" style="padding:10px 12px;margin-bottom:8px;">
                    <span class="rf-pill rf-pill-blue">{row.stage}</span>
                    <strong>{row.name}</strong>
                    <div style="color:#64748b;font-size:12px;margin-top:2px;">{row.job_title} · {format_timestamp(row.updated_at)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_wecom() -> None:
    render_page_header(
        "WeCom Integration",
        "企业微信群",
        "配置企业微信群机器人 Webhook，测试消息发送，并把候选人推荐摘要推送到面试官群。",
    )

    apply_wecom_session_defaults()
    enabled = bool(st.session_state.get("wecom_notify_enabled", False))
    webhook = str(st.session_state.get("wecom_webhook_url", ""))
    message_type = str(st.session_state.get("wecom_message_type", "markdown"))
    mode = "真实发送" if enabled and webhook else "Mock演示"
    webhook_status = "已填写" if webhook else "未填写"

    st.markdown(
        f"""
        <div class="rf-status-grid">
            <div class="rf-status">
                <div class="rf-status-label">连接模式</div>
                <div class="rf-status-value">{mode}</div>
            </div>
            <div class="rf-status">
                <div class="rf-status-label">Webhook</div>
                <div class="rf-status-value">{webhook_status}</div>
            </div>
            <div class="rf-status">
                <div class="rf-status-label">消息格式</div>
                <div class="rf-status-value">{message_type}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.46, 0.54], gap="large")
    with left:
        st.markdown(
            """
            <div class="rf-card">
                <div class="rf-section-title">连接配置</div>
                <div class="rf-section-copy">
                    面试演示默认使用 Mock 模式；填写企业微信群机器人 Webhook 并开启真实发送后，
                    候选人推荐和测试消息会发到对应群聊。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("wecom-config-form"):
            enabled_input = st.toggle("启用真实发送", value=enabled)
            webhook_input = st.text_input(
                "企业微信群机器人 Webhook",
                value=webhook,
                type="password",
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...",
            )
            message_type_input = st.selectbox(
                "消息类型",
                ["markdown", "text"],
                index=0 if message_type != "text" else 1,
            )
            timeout_input = st.number_input(
                "超时时间（秒）",
                min_value=3,
                max_value=30,
                value=int(float(os.getenv("WECOM_TIMEOUT_SECONDS", "10"))),
                step=1,
            )
            saved = st.form_submit_button("保存本次运行配置", type="primary", use_container_width=True)
        if saved:
            st.session_state["wecom_notify_enabled"] = enabled_input
            st.session_state["wecom_webhook_url"] = webhook_input.strip()
            st.session_state["wecom_message_type"] = message_type_input
            st.session_state["wecom_timeout_seconds"] = str(timeout_input)
            apply_wecom_session_env()
            st.success("企业微信群配置已保存，本次运行立即生效。")

        st.markdown(
            """
            <div class="rf-note">
                说明：普通企业微信群机器人适合作为“推送出口”，不能自动监听群内全部消息。
                群内反馈仍通过“面试官反馈”页面粘贴解析，后续可升级为企业微信自建应用回调。
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class="rf-card">
                <div class="rf-section-title">发送测试</div>
                <div class="rf-section-copy">
                    用于确认 Webhook 是否可用。Mock 模式下会展示即将发送的 payload，不会访问外部服务。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        default_message = """【RecruitFlow AI 测试消息】
> 企业微信群机器人已接入
> 用途：候选人推荐、面试反馈提醒、同步异常通知

收到这条消息说明 Webhook 可用。"""
        message = st.text_area("测试消息内容", default_message, height=180)
        col1, col2 = st.columns(2)
        with col1:
            preview = st.button("预览Payload", use_container_width=True)
        with col2:
            send = st.button("发送测试消息", type="primary", use_container_width=True)

        if preview:
            st.json(build_payload(message, message_type))

        if send:
            apply_wecom_session_env()
            adapter = WeComAdapter.from_env()
            result = adapter.send(message, message_type)
            db.add_integration_log(
                "wecom_test",
                result.get("status", "unknown"),
                request_data={"message_type": message_type, "message": message},
                response_data=result,
                db_path=DB_PATH,
            )
            if result.get("status") == "sent":
                st.success("测试消息已发送到企业微信群。")
            elif result.get("status") == "mock":
                st.info("当前为 Mock 模式，未真实发送；Payload 已生成并写入同步日志。")
                st.json(result.get("payload", {}))
            elif result.get("status") == "config_error":
                st.error(result.get("message", "企业微信配置不完整。"))
            else:
                st.error(f"发送失败：{result.get('error') or result.get('message') or result}")


def render_events() -> None:
    render_page_header(
        "Event Log",
        "事件日志",
        "查看简历确认、反馈确认、阻塞流转和同步记录，帮助答辩时说明数据闭环。",
    )

    events = prepare_events(db.events_view(DB_PATH))
    if events.empty:
        st.info("暂无事件。完成候选人入库或反馈确认后会自动生成。")
    else:
        filtered = render_event_filters(events)
        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("事件ID", format="#%d"),
                "application_id": st.column_config.NumberColumn("申请ID", format="#%d"),
                "event_type": "事件类型",
                "old_stage": "原阶段",
                "new_stage": "新阶段",
                "confidence": st.column_config.NumberColumn("置信度", format="%.0%%"),
                "status": "状态",
                "created_at": st.column_config.DatetimeColumn("时间", format="YYYY-MM-DD HH:mm"),
            },
        )

    st.subheader("腾讯文档 Mock 文件")
    mock_path = "data/mock_tencent_docs.csv"
    if os.path.exists(mock_path):
        st.dataframe(pd.read_csv(mock_path), use_container_width=True, hide_index=True)
    else:
        st.info("暂无同步记录。")

    st.subheader("外部集成日志")
    logs = prepare_integration_logs(db.integration_logs_view(DB_PATH))
    if logs.empty:
        st.info("暂无企业微信或文档同步日志。")
    else:
        st.dataframe(
            logs[
                [
                    "id",
                    "event_ref",
                    "integration_type",
                    "status",
                    "error_message",
                    "request_preview",
                    "response_preview",
                    "created_at",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("日志ID", format="#%d"),
                "event_ref": "事件ID",
                "integration_type": "集成类型",
                "status": "状态",
                "error_message": "错误信息",
                "request_preview": "请求摘要",
                "response_preview": "响应摘要",
                "created_at": st.column_config.DatetimeColumn("时间", format="YYYY-MM-DD HH:mm"),
            },
        )


def render_settings() -> None:
    render_page_header(
        "Job Setup",
        "岗位配置",
        "维护 Demo 岗位和 JD。MVP 默认只需要少量岗位即可演示完整闭环。",
    )

    with st.form("job-form"):
        title = st.text_input("岗位名称", "AI产品经理")
        owner = st.text_input("招聘负责人", "王芳")
        jd = st.text_area(
            "岗位JD",
            "负责AI Agent产品规划，要求3年以上B端/SaaS经验，熟悉数据分析、流程自动化和跨部门协作。",
            height=160,
        )
        if st.form_submit_button("新增岗位", type="primary"):
            db.add_job(title, jd, owner, DB_PATH)
            st.success("岗位已创建")

    jobs = db.list_jobs(DB_PATH)
    st.dataframe(jobs, use_container_width=True, hide_index=True)


def render_candidate_filters(data: pd.DataFrame) -> pd.DataFrame:
    st.markdown("#### 筛选")
    f1, f2, f3, f4 = st.columns([0.22, 0.22, 0.22, 0.34])
    with f1:
        stages = st.multiselect("阶段", STAGE_ORDER, default=[])
    with f2:
        jobs = st.multiselect("岗位", sorted(data["job_title"].dropna().unique().tolist()), default=[])
    with f3:
        owners = st.multiselect("负责人", sorted(data["owner_display"].dropna().unique().tolist()), default=[])
    with f4:
        keyword = st.text_input("搜索", placeholder="姓名 / 岗位 / 学校 / 邮箱 / 手机")

    s1, s2, _ = st.columns([0.25, 0.25, 0.5])
    with s1:
        min_score, max_score = st.slider("匹配分", 0, 100, (0, 100), step=5)
    with s2:
        active_only = st.toggle("仅看活跃流程", value=False)

    view = data.copy()
    if stages:
        view = view[view["stage"].isin(stages)]
    if jobs:
        view = view[view["job_title"].isin(jobs)]
    if owners:
        view = view[view["owner_display"].isin(owners)]
    if active_only:
        view = view[view["stage"].isin(ACTIVE_STAGES)]
    view = view[view["score_filled"].between(min_score, max_score)]
    if keyword:
        searchable = ["name", "job_title", "school", "email", "phone", "owner_display"]
        mask = view[searchable].astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        view = view[mask]
    return view


def render_dashboard_filters(data: pd.DataFrame) -> pd.DataFrame:
    f1, f2, f3 = st.columns([0.32, 0.32, 0.36])
    with f1:
        jobs = st.multiselect("看板岗位", sorted(data["job_title"].dropna().unique().tolist()), default=[])
    with f2:
        owners = st.multiselect("负责人", sorted(data["owner_display"].dropna().unique().tolist()), default=[])
    with f3:
        show_terminal = st.toggle("包含终态候选人", value=True)

    view = data.copy()
    if jobs:
        view = view[view["job_title"].isin(jobs)]
    if owners:
        view = view[view["owner_display"].isin(owners)]
    if not show_terminal:
        view = view[~view["stage"].isin(TERMINAL_STAGES)]
    return view


def render_event_filters(events: pd.DataFrame) -> pd.DataFrame:
    f1, f2, f3 = st.columns([0.28, 0.24, 0.48])
    with f1:
        event_types = st.multiselect("事件类型", sorted(events["event_type"].dropna().unique().tolist()), default=[])
    with f2:
        statuses = st.multiselect("状态", sorted(events["status"].dropna().unique().tolist()), default=[])
    with f3:
        keyword = st.text_input("搜索事件内容", placeholder="阶段 / 原文 / JSON 内容")

    view = events.copy()
    if event_types:
        view = view[view["event_type"].isin(event_types)]
    if statuses:
        view = view[view["status"].isin(statuses)]
    if keyword:
        mask = view.astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        view = view[mask]
    return view


def render_candidate_summary(filtered: pd.DataFrame, data: pd.DataFrame) -> None:
    active = int(filtered["stage"].isin(ACTIVE_STAGES).sum())
    offer = int(filtered["stage"].isin(["Offer审批", "Offer已发", "待入职", "已入职"]).sum())
    avg_score = filtered["score"].dropna().mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("筛选结果", len(filtered), delta=f"总计 {len(data)}")
    c2.metric("活跃流程", active)
    c3.metric("Offer/入职", offer)
    c4.metric("平均匹配分", "N/A" if pd.isna(avg_score) else f"{avg_score:.1f}")


def render_dashboard_kpis(data: pd.DataFrame) -> None:
    active = int(data["stage"].isin(ACTIVE_STAGES).sum())
    waiting_feedback = int(data["stage"].astype(str).str.contains("待反馈", na=False).sum())
    offer = int(data["stage"].isin(["Offer审批", "Offer已发", "待入职", "已入职"]).sum())
    avg_score = data["score"].dropna().mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("候选人总数", len(data))
    c2.metric("活跃流程", active)
    c3.metric("待反馈", waiting_feedback)
    c4.metric("平均匹配分", "N/A" if pd.isna(avg_score) else f"{avg_score:.1f}")

    if offer:
        st.markdown(
            f'<span class="rf-pill rf-pill-green">Offer/入职 {offer}</span>',
            unsafe_allow_html=True,
        )


def prepare_applications(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return data
    view = data.copy()
    view["updated_at"] = pd.to_datetime(view["updated_at"], errors="coerce")
    view["score"] = pd.to_numeric(view["score"], errors="coerce")
    view["score_filled"] = view["score"].fillna(0)
    view["owner_display"] = view["owner"].fillna("未分配").replace("", "未分配")
    view["stage"] = pd.Categorical(view["stage"], categories=STAGE_ORDER, ordered=True)
    return view.sort_values(["stage", "updated_at"], ascending=[True, False])


def prepare_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    view = events.copy()
    view["created_at"] = pd.to_datetime(view["created_at"], errors="coerce")
    view["confidence"] = pd.to_numeric(view["confidence"], errors="coerce")
    return view.sort_values("created_at", ascending=False)


def prepare_integration_logs(logs: pd.DataFrame) -> pd.DataFrame:
    if logs.empty:
        return logs
    view = logs.copy()
    view["created_at"] = pd.to_datetime(view["created_at"], errors="coerce")
    view["event_ref"] = view["event_id"].apply(format_optional_id)
    view["error_message"] = view["error_message"].fillna("")
    view["request_preview"] = view["request_data"].apply(compact_json_preview)
    view["response_preview"] = view["response_data"].apply(compact_json_preview)
    return view.sort_values("created_at", ascending=False)


def format_optional_id(value: object) -> str:
    if pd.isna(value):
        return "-"
    try:
        return f"#{int(value)}"
    except (TypeError, ValueError):
        return str(value)


def compact_json_preview(value: object, limit: int = 160) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def stage_count_frame(data: pd.DataFrame) -> pd.DataFrame:
    counts = data.groupby("stage", observed=False).size().reset_index(name="count")
    counts = counts[counts["count"] > 0]
    counts["stage_group"] = counts["stage"].astype(str).apply(stage_group)
    return counts


def stage_group(stage: str) -> str:
    if stage in TERMINAL_STAGES:
        return "终态"
    if stage in ["Offer审批", "Offer已发", "待入职", "已入职"]:
        return "Offer/入职"
    return "活跃"


def render_pills(items: list[str], tone: str = "blue") -> None:
    html = "".join(f'<span class="rf-pill rf-pill-{tone}">{item}</span>' for item in items)
    st.markdown(html, unsafe_allow_html=True)


def current_wecom_enabled() -> str:
    value = st.session_state.get("wecom_notify_enabled")
    if value is None:
        value = os.getenv("WECOM_NOTIFY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    return "true" if value else "false"


def apply_wecom_session_defaults() -> None:
    if "wecom_notify_enabled" not in st.session_state:
        st.session_state["wecom_notify_enabled"] = os.getenv("WECOM_NOTIFY_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if "wecom_webhook_url" not in st.session_state:
        st.session_state["wecom_webhook_url"] = os.getenv("WECOM_WEBHOOK_URL", "")
    if "wecom_message_type" not in st.session_state:
        st.session_state["wecom_message_type"] = os.getenv("WECOM_MESSAGE_TYPE", "markdown")
    if "wecom_timeout_seconds" not in st.session_state:
        st.session_state["wecom_timeout_seconds"] = os.getenv("WECOM_TIMEOUT_SECONDS", "10")


def apply_wecom_session_env() -> None:
    apply_wecom_session_defaults()
    os.environ["WECOM_NOTIFY_ENABLED"] = "true" if st.session_state.get("wecom_notify_enabled") else "false"
    os.environ["WECOM_WEBHOOK_URL"] = str(st.session_state.get("wecom_webhook_url", ""))
    os.environ["WECOM_MESSAGE_TYPE"] = str(st.session_state.get("wecom_message_type", "markdown"))
    os.environ["WECOM_TIMEOUT_SECONDS"] = str(st.session_state.get("wecom_timeout_seconds", "10"))


def format_timestamp(value: object) -> str:
    if pd.isna(value):
        return "时间待确认"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%m-%d %H:%M")
    return str(value)


def seed_demo_candidate() -> None:
    jobs = db.list_jobs(DB_PATH)
    if jobs.empty:
        ensure_demo_job()
        jobs = db.list_jobs(DB_PATH)
    job = jobs.iloc[0]
    result = parse_resume_with_jd(DEMO_RESUME, str(job["title"]), str(job["jd"]))
    confirm_resume_intake(int(job["id"]), result, DEMO_RESUME, owner=str(job.get("owner") or "王芳"))


def ensure_demo_job() -> None:
    jobs = db.list_jobs(DB_PATH)
    if jobs.empty:
        db.add_job(
            "AI产品经理",
            "负责AI Agent招聘运营产品设计，要求3年以上B端产品经验，熟悉SaaS、数据分析、流程自动化，有AI产品经验优先。",
            "王芳",
            DB_PATH,
        )


if __name__ == "__main__":
    main()
