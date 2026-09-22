#!/usr/bin/env python3
"""Demo 04: Streamlit UI for Issue Triage with application-controlled function calling."""

from __future__ import annotations

import os

import streamlit as st

from demo_common import load_environment, model_name, openai_client
from triage_workflow import TriageResult, triage_issue

DEFAULT_ISSUE = """Nút thanh toán trả HTTP 500 với mọi thẻ Visa từ 14:30.
Hãy triage issue và cho biết team nào cần xử lý."""

st.set_page_config(
    page_title="Issue Triage — Function Calling",
    page_icon="IT",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    [data-testid="stFormSubmitButton"] > button {
        background-color: #15803d;
        color: #ffffff;
    }
    [data-testid="stFormSubmitButton"] > button:hover {
        background-color: #166534;
        color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



def render_result(result: TriageResult) -> None:
    """Render validated triage data and the full application-controlled trace."""
    triage = result.triage
    status_column, severity_column, urgent_column = st.columns(3)
    status_column.metric("Trạng thái", triage.status)
    severity_column.metric("Mức độ", triage.severity or "Chưa xác định")
    urgent_column.metric("Phản hồi khẩn", "Có" if triage.needs_urgent_response else "Không")

    if triage.component:
        component_column, owner_column = st.columns(2)
        component_column.metric("Component đã xác thực", triage.component)
        owner_column.metric("Team phụ trách", triage.owner or "Chưa xác định")

    with st.expander("Trace function calling", expanded=True):
        if not result.tool_traces:
            st.info("Model không gọi tool vì issue chưa xác định component được hỗ trợ.")
        for index, trace in enumerate(result.tool_traces, start=1):
            st.markdown(f"**{index}. Model yêu cầu tool** `{trace.name}`")
            st.json({"id": trace.call_id, "arguments": trace.arguments})
            st.markdown("**2. Application validate và thực thi**")
            st.json(trace.result)
        st.markdown("**3. Tool result được gửi lại model → final response**")

    st.subheader("Kết quả IssueTriage đã validate")
    st.write(triage.reason)
    st.caption("Pydantic đã kiểm tra schema và application đã đối chiếu owner với tool result.")
    st.json(triage.model_dump())


def main() -> None:
    load_environment()

    with st.sidebar:
        st.header("Runtime")
        st.write("OpenAI-compatible API")
        st.code(os.getenv("OPENAI_BASE_URL") or "Chưa cấu hình URL", language=None)
        st.write("Model")
        st.code(os.getenv("OPENAI_MODEL") or "Chưa cấu hình model", language=None)
        st.divider()
        st.write(
            "Application chỉ thực thi get_component_owner cho payment, identity và search."
        )

    st.title("Issue Triage")
    st.write(
        "Model đề xuất tool call; application kiểm tra rồi mới thực thi và validate "
        "IssueTriage bằng Pydantic."
    )

    with st.form("issue-triage-form"):
        issue = st.text_area(
            "Mô tả issue",
            value=DEFAULT_ISSUE,
            height=220,
            help="Nêu symptom, phạm vi ảnh hưởng và thời điểm bắt đầu nếu có.",
        )
        submitted = st.form_submit_button("Phân loại issue", type="primary", use_container_width=True)

    if not submitted:
        return
    if not issue.strip():
        st.error("Nhập mô tả issue trước khi chạy triage.")
        return

    try:
        with st.spinner("Đang gọi model, xử lý tool request và validate IssueTriage…"):
            result = triage_issue(openai_client(), model_name(), issue.strip())
    except Exception as error:
        st.error(f"Triage không hoàn tất: {error}")
        st.info("Kiểm tra OPENAI_BASE_URL, OPENAI_MODEL và quyền truy cập model trong .env.")
        return

    st.success("Application đã hoàn tất triage, function calling và Pydantic validation.")
    render_result(result)


if __name__ == "__main__":
    main()
