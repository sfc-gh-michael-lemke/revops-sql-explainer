import streamlit as st

st.set_page_config(
    page_title="RevOps SQL Explainer",
    page_icon=":material/code:",
    layout="wide",
)

MODELS = [
    "llama3.1-8b",
    "llama3.1-70b",
    "claude-3-5-sonnet",
    "mistral-large2",
]

SYSTEM_PROMPT = "Explain this SQL to a non-technical RevOps user. Cover: what it does in business terms, how it works step by step, tables referenced and any permission concerns, business considerations (filters, aggregations, hardcoded values), and whether data looks normalized or denormalized. Use markdown headers and bullets. Be concise."


def explain_sql(sql_text: str, model: str, user_role: str | None = None) -> str:
    prompt = SYSTEM_PROMPT + "\n\n```sql\n" + sql_text + "\n```"
    if user_role:
        prompt += f"\n\nUser role: {user_role}. Assess access."
    escaped = prompt.replace("\\", "\\\\").replace("'", "''")
    session = st.connection("snowflake").session()
    result = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{escaped}') AS response"
    ).collect()
    return result[0]["RESPONSE"]


st.title("RevOps SQL Explainer")
st.caption(
    "Paste any SQL statement and get a clear, business-friendly explanation."
)

with st.sidebar:
    model = st.selectbox(
        "AI model",
        MODELS,
        index=0,
        help="llama3.1-8b is fastest (~10s). llama3.1-70b and claude are more detailed but slower (~30-60s).",
    )
    user_role = st.text_input(
        "Your Snowflake role (optional)",
        placeholder="e.g. SALES_ANALYST_RL",
        help="If provided, the explanation will assess access to referenced tables",
    )
    st.caption("Built for RevOps by RevOps")

sql_input = st.text_area(
    "Paste your SQL here",
    height=250,
    placeholder="SELECT o.opportunity_name, a.account_name, ...",
)

if st.button("Explain this query", type="primary", icon=":material/lightbulb:"):
    if not sql_input.strip():
        st.warning("Paste a SQL statement first.")
    else:
        with st.status("Analyzing your SQL...", expanded=True) as status:
            st.write(f"Using {model} - this typically takes 10-30 seconds...")
            response = explain_sql(
                sql_input.strip(),
                model,
                user_role.strip() if user_role else None,
            )
            status.update(label="Analysis complete", state="complete")
        st.markdown(response)
