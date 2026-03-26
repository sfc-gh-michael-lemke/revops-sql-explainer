import streamlit as st

st.set_page_config(
    page_title="RevOps SQL Explainer",
    page_icon=":material/code:",
    layout="wide",
)

MODELS = [
    "llama3.1-70b",
    "claude-3-5-sonnet",
    "mistral-large2",
]

SYSTEM_PROMPT = """You are a SQL analyst for Revenue Operations. Explain SQL to business users who don't write SQL.

Given a SQL statement, respond with these sections using markdown:

## What this query does
Plain business English. Use RevOps terms (pipeline, ARR, bookings). No jargon.

## How it works
Numbered steps explaining each clause in business terms.

## Permission check
List all tables/views referenced. Flag sensitive schemas or WRITE operations (INSERT/UPDATE/DELETE/DROP).

## Business considerations
- Date filters limiting data
- Aggregations hiding detail
- NULL handling excluding records
- Hardcoded values needing updates
- Filters silently excluding data

## Data normalization
Is the data denormalized? Many joins (normalized) or wide flat tables (denormalized)? JSON/VARIANT columns?

Be concise. Use bullets and bold for scannability."""


def explain_sql(sql_text: str, model: str, user_role: str | None = None) -> str:
    prompt = f"Analyze this SQL:\n\n```sql\n{sql_text}\n```"
    if user_role:
        prompt += f"\n\nUser's Snowflake role: {user_role}. Assess access to referenced objects."
    full_prompt = SYSTEM_PROMPT + "\n\n" + prompt
    # Escape single quotes for SQL string literal
    escaped = full_prompt.replace("'", "''")
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
        help="llama3.1-70b is fastest. claude-3-5-sonnet is most detailed.",
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
            st.write("Sending to AI model...")
            response = explain_sql(
                sql_input.strip(),
                model,
                user_role.strip() if user_role else None,
            )
            status.update(label="Analysis complete", state="complete")
        st.markdown(response)
