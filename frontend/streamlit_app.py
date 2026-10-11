"""Streamlit UI for the local analytics agent."""
import json
import streamlit as st
from backend.app import AnalyzeRequest, _run

st.set_page_config(page_title="AI 数据运营分析 Agent", layout="wide")
st.title("AI 数据运营分析 Agent")
st.caption("电商运营 MVP · SQLite 只读演示 · 结果可追溯")
examples = ["最近三个月各渠道的销售额", "最近三个月各渠道的付费率", "不同城市的客单价", "注册后 7 天支付转化率"]
question = st.text_area("用中文描述你的分析问题", value=examples[0], height=90)
st.write("示例：", " · ".join(examples))

if st.button("开始分析", type="primary"):
    with st.spinner("正在解析问题、匹配口径并执行只读查询…"):
        result = _run(AnalyzeRequest(query=question))
    if result.get("next_action") == "clarify":
        st.warning(result["clarification_question"])
        st.json(result["intent"])
    elif result.get("error"):
        st.error(result["error"])
        st.code(result.get("sql", ""), language="sql")
    else:
        st.success(f"分析完成：{result['intent']['time']['start']} 至 {result['intent']['time']['end']}")
        left, right = st.columns(2)
        with left:
            st.subheader("指标口径")
            for item in result["semantic_matches"]:
                st.write(f"**{item['name']}**：{item['definition']}")
        with right:
            st.subheader("数据质量")
            st.write(result["quality"])
        tab1, tab2, tab3 = st.tabs(["分析报告", "数据结果", "SQL 与过程"])
        with tab1:
            report = result["report"]
            st.subheader("核心发现")
            for fact in report["facts"]:
                st.write(f"- {fact['text']}（证据：`{fact['evidence_id']}`）")
            st.subheader("可能原因")
            for item in report["hypotheses"]:
                st.write(f"- {item}")
            st.subheader("运营建议")
            for item in report["recommendations"]:
                st.write(f"- {item}")
        with tab2:
            rows = result["data"]["rows"]
            st.dataframe(rows, use_container_width=True)
            st.download_button("下载 JSON", json.dumps(rows, ensure_ascii=False, indent=2), file_name="analysis-result.json", mime="application/json")
        with tab3:
            st.write("安全检查：", result["security"])
            st.code(result["sql"], language="sql")
            st.json(result["intent"])
