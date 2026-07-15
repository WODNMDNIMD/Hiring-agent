from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from recruitflow.ai.feedback_parser import parse_feedback
from recruitflow.ai.resume_parser import parse_resume_with_jd
from recruitflow.core import database as db
from recruitflow.core.models import Stage
from recruitflow.core.workflow import confirm_feedback, confirm_resume_intake
from recruitflow.utils.files import extract_text

load_dotenv()

DB_PATH = os.getenv("DATABASE_URL", "data/recruitflow.db")


st.set_page_config(
    page_title="RecruitFlow AI",
    page_icon="RF",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    db.init_db(DB_PATH)
    ensure_demo_job()
    render_sidebar()
    page = st.session_state.get("page", "AI候选人录入")
    if page == "AI候选人录入":
        render_intake()
    elif page == "面试官反馈":
        render_feedback()
    elif page == "候选人台账":
        render_candidates()
    elif page == "招聘看板":
        render_dashboard()
    elif page == "事件与同步日志":
        render_events()
    else:
        render_settings()


def render_sidebar() -> None:
    st.sidebar.title("RecruitFlow AI")
    st.sidebar.caption("招聘数据智能记录与运营助手")
    pages = ["AI候选人录入", "面试官反馈", "候选人台账", "招聘看板", "事件与同步日志", "岗位配置"]
    choice = st.sidebar.radio("模块", pages, key="page")
    st.sidebar.divider()
    st.sidebar.write("当前模式")
    st.sidebar.code(f"AI_PROVIDER={os.getenv('AI_PROVIDER', 'mock')}\nTENCENT_DOCS_MODE={os.getenv('TENCENT_DOCS_MODE', 'mock')}")
    if choice:
        st.sidebar.caption("MVP默认使用Mock能力，确保面试现场不依赖外部授权。")


def render_intake() -> None:
    st.title("AI候选人录入")
    st.caption("上传简历或粘贴简历文本，选择岗位后自动生成结构化信息、匹配分析和推荐语。")
    jobs = db.list_jobs(DB_PATH)
    if jobs.empty:
        st.warning("请先创建岗位。")
        return

    left, right = st.columns([0.42, 0.58], gap="large")
    with left:
        job_options = {f"{row.title}｜{row.owner or '未分配'}": int(row.id) for row in jobs.itertuples()}
        selected_label = st.selectbox("目标岗位", list(job_options.keys()))
        job_id = job_options[selected_label]
        job = jobs[jobs["id"] == job_id].iloc[0]
        uploaded = st.file_uploader("上传简历", type=["pdf", "docx", "txt"])
        default_resume = """姓名：李明
电话：13800138000
邮箱：liming@example.com
本科，4年B端产品经验，熟悉SaaS、AI Agent、数据分析和SQL。
最近负责招聘运营自动化项目，完成候选人台账、流程看板和消息通知设计。
期望薪资：20-25K，已离职，可两周内到岗。
"""
        resume_text = st.text_area("或直接粘贴简历文本", default_resume, height=260)
        owner = st.text_input("招聘负责人", value=str(job.get("owner") or "王芳"))
        parse_clicked = st.button("AI解析并生成推荐语", type="primary", use_container_width=True)

    with right:
        if uploaded:
            resume_text = extract_text(uploaded.name, uploaded.getvalue())
        if parse_clicked:
            st.session_state["intake_raw_resume"] = resume_text
            st.session_state["intake_result"] = parse_resume_with_jd(resume_text, str(job["title"]), str(job["jd"]))
            st.session_state["intake_job_id"] = job_id
            st.session_state["intake_owner"] = owner
        result = st.session_state.get("intake_result")
        if result:
            st.subheader("AI解析结果")
            c1, c2, c3 = st.columns(3)
            c1.metric("候选人", result.candidate.name)
            c2.metric("匹配分", result.match.score)
            c3.metric("建议", result.match.recommendation_level)
            with st.expander("结构化候选人信息", expanded=True):
                st.json(result.candidate.model_dump())
            with st.expander("匹配点与风险点", expanded=True):
                st.write("匹配点")
                st.write(result.match.matched_points or ["待确认"])
                st.write("风险点")
                st.write(result.match.risk_points or ["暂无明显风险"])
            st.text_area("标准化推荐语", result.match.recommendation_text, height=160)
            if st.button("确认入库并推送面试官群", type="primary", use_container_width=True):
                output = confirm_resume_intake(
                    int(st.session_state["intake_job_id"]),
                    result,
                    st.session_state.get("intake_raw_resume", ""),
                    owner=st.session_state.get("intake_owner"),
                )
                st.success(f"已创建/更新候选人并写入事件日志：Application #{output['application_id']}")
                st.session_state.pop("intake_result", None)
        else:
            st.info("点击左侧按钮后，这里会展示 AI 结构化结果。")


def render_feedback() -> None:
    st.title("面试官反馈收件箱")
    st.caption("粘贴群内反馈，AI识别动作意图，HR确认后更新候选人流程状态。")
    apps = db.applications_view(DB_PATH)
    if apps.empty:
        st.info("暂无候选人，请先完成一次 AI 候选人录入。")
        return
    options = {
        f"#{row.application_id} {row.name}｜{row.job_title}｜{row.stage}": int(row.application_id)
        for row in apps.itertuples()
    }
    selected = st.selectbox("选择候选申请", list(options.keys()))
    app_id = options[selected]
    current_stage = str(apps[apps["application_id"] == app_id].iloc[0]["stage"])
    raw = st.text_area("粘贴面试官反馈", "李明可以约面，建议安排下周二下午，重点考察项目推进能力。", height=160)
    if st.button("AI解析反馈", type="primary"):
        st.session_state["feedback_result"] = parse_feedback(raw)
        st.session_state["feedback_raw"] = raw
        st.session_state["feedback_app_id"] = app_id
        st.session_state["feedback_stage"] = current_stage
    result = st.session_state.get("feedback_result")
    if result:
        st.subheader("反馈解析结果")
        c1, c2, c3 = st.columns(3)
        c1.metric("动作意图", result.intent)
        c2.metric("下一状态", result.next_stage or "待确认")
        c3.metric("置信度", f"{result.confidence:.0%}")
        st.json(result.model_dump())
        if result.invitation_message:
            st.text_area("候选人邀约话术", result.invitation_message, height=120)
        if st.button("确认更新流程状态", type="primary"):
            output = confirm_feedback(
                int(st.session_state["feedback_app_id"]),
                st.session_state["feedback_stage"],  # type: ignore[arg-type]
                result,
                st.session_state["feedback_raw"],
            )
            if output["status"] == "blocked":
                st.warning(output["message"])
            else:
                st.success(f"状态已更新：{output['old_stage']} -> {output['new_stage']}")
            st.session_state.pop("feedback_result", None)


def render_candidates() -> None:
    st.title("候选人台账")
    data = db.applications_view(DB_PATH)
    if data.empty:
        st.info("暂无候选人。")
        return
    stages = ["全部"] + sorted(data["stage"].dropna().unique().tolist())
    stage = st.selectbox("按阶段筛选", stages)
    keyword = st.text_input("搜索姓名 / 岗位 / 学校")
    view = data.copy()
    if stage != "全部":
        view = view[view["stage"] == stage]
    if keyword:
        mask = view.astype(str).apply(lambda col: col.str.contains(keyword, case=False, na=False)).any(axis=1)
        view = view[mask]
    st.dataframe(view, use_container_width=True, hide_index=True)


def render_dashboard() -> None:
    st.title("招聘看板")
    data = db.applications_view(DB_PATH)
    if data.empty:
        st.info("暂无数据，完成候选人录入后看板会自动刷新。")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("候选人总数", len(data))
    c2.metric("待面试/安排", int(data["stage"].str.contains("安排|反馈", regex=True).sum()))
    c3.metric("Offer阶段", int(data["stage"].str.contains("Offer|待入职|已入职", regex=True).sum()))
    c4.metric("平均匹配分", f"{data['score'].dropna().mean():.1f}")

    left, right = st.columns(2, gap="large")
    with left:
        stage_counts = data.groupby("stage").size().reset_index(name="count")
        st.plotly_chart(px.bar(stage_counts, x="stage", y="count", title="招聘阶段漏斗"), use_container_width=True)
    with right:
        job_counts = data.groupby("job_title").size().reset_index(name="count")
        st.plotly_chart(px.pie(job_counts, names="job_title", values="count", title="岗位候选人分布"), use_container_width=True)


def render_events() -> None:
    st.title("事件与同步日志")
    events = db.events_view(DB_PATH)
    st.subheader("招聘事件")
    st.dataframe(events, use_container_width=True, hide_index=True)
    st.subheader("腾讯文档 Mock 文件")
    mock_path = "data/mock_tencent_docs.csv"
    if os.path.exists(mock_path):
        st.dataframe(pd.read_csv(mock_path), use_container_width=True, hide_index=True)
    else:
        st.info("暂无同步记录。")


def render_settings() -> None:
    st.title("岗位配置")
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
    st.dataframe(db.list_jobs(DB_PATH), use_container_width=True, hide_index=True)


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

