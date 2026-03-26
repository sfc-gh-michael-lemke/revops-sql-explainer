import json
import streamlit as st

st.set_page_config(
    page_title="RevOps SQL Explainer",
    page_icon=":material/code:",
    layout="wide",
)

MODELS = [
    "claude-3-5-sonnet",
    "llama3.1-70b",
    "mistral-large2",
]

SYSTEM_PROMPT = """You are a SQL analyst for a Revenue Operations team. Your audience is business users who do not write SQL.

Given a SQL statement, provide a structured analysis with these exact sections:

## What this query does
Explain in plain business English what data this query retrieves or modifies. Use terms a RevOps analyst would understand (e.g., "pipeline", "bookings", "ARR", "quota attainment"). Avoid technical jargon.

## How it works (step by step)
Walk through the query logic in numbered steps. Explain each clause (FROM, JOIN, WHERE, GROUP BY, etc.) in business terms. For example, instead of "LEFT JOIN on account_id", say "Connects each opportunity to its parent account, keeping opportunities even if the account record is missing."

## Permission check
List every table and view referenced in the query. For each one, note:
- The fully qualified name (database.schema.table)
- Whether it appears to be a production, staging, or dev table based on naming conventions
- Flag any tables in sensitive schemas (e.g., containing "sensitive", "pii", "confidential", "hr", "compensation" in the name)
- If the query uses INSERT, UPDATE, DELETE, MERGE, CREATE, DROP, or ALTER, warn prominently that this is a WRITE operation

## Business considerations
Call out important things a RevOps person should know:
- Date filters or time windows that limit the data
- Aggregations that roll up detail (and what detail is lost)
- NULL handling that could exclude records
- CASE statements that apply business logic or categorization
- Hardcoded values or magic numbers that may need updating
- Whether the query could produce duplicate rows
- Any filters that might silently exclude data (e.g., WHERE status != 'Deleted')

## Data normalization assessment
Assess whether the data appears denormalized:
- Are there repeated values that suggest flattened/denormalized tables?
- Does the query join many tables together (suggesting normalized source data)?
- Are there wide tables with many columns from different domains?
- Are there embedded arrays, JSON, or VARIANT columns?
- Recommend whether this pattern is appropriate for the apparent use case

Keep the tone professional but accessible. Use bullet points and bold text for scannability."""


def explain_sql(sql_text: str, model: str, user_role: str | None = None) -> str:
    prompt = f"Analyze this SQL statement:\n\n```sql\n{sql_text}\n```"
    if user_role:
        prompt += (
            f"\n\nThe user's current Snowflake role is: {user_role}. "
            "Consider whether this role likely has access to the referenced objects "
            "based on common naming conventions."
        )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    messages_json = json.dumps(messages).replace("'", "\\'")
    session = st.connection("snowflake").session()
    result = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', PARSE_JSON($${messages_json}$$)) AS response"
    ).collect()
    return result[0]["RESPONSE"]


st.title("RevOps SQL Explainer")
st.caption(
    "Paste any SQL statement and get a clear, business-friendly explanation "
    "of what it does, how it works, and what to watch out for."
)

with st.sidebar:
    model = st.selectbox(
        "AI model",
        MODELS,
        index=0,
        help="claude-3-5-sonnet is recommended for best results",
    )
    user_role = st.text_input(
        "Your Snowflake role (optional)",
        placeholder="e.g. SALES_ANALYST_RL",
        help="If provided, the explanation will assess whether this role likely has access to the referenced tables",
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
        with st.spinner("Analyzing..."):
            response = explain_sql(
                sql_input.strip(),
                model,
                user_role.strip() if user_role else None,
            )
            st.markdown(response)
