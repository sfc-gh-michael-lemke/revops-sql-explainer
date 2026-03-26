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
    session.sql("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 300").collect()
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

SAMPLE_QUERIES = {
    "Pipeline by rep": """SELECT
    u.full_name AS rep_name,
    u.team,
    COUNT(o.opportunity_id) AS deal_count,
    SUM(o.amount) AS total_pipeline,
    SUM(CASE WHEN o.forecast_category = 'Commit' THEN o.amount ELSE 0 END) AS commit_amount,
    AVG(DATEDIFF('day', o.created_date, o.close_date)) AS avg_sales_cycle
FROM salesforce.opportunity o
JOIN salesforce.user u ON o.owner_id = u.user_id
JOIN salesforce.account a ON o.account_id = a.account_id
WHERE o.stage_name NOT IN ('Closed Won', 'Closed Lost')
  AND o.close_date BETWEEN '2025-01-01' AND '2025-03-31'
  AND o.is_deleted = FALSE
  AND a.type != 'Partner'
GROUP BY 1, 2
HAVING SUM(o.amount) > 100000
ORDER BY total_pipeline DESC""",
    "Quota attainment": """SELECT
    q.rep_name,
    q.region,
    q.quota_amount,
    COALESCE(w.won_amount, 0) AS bookings,
    ROUND(COALESCE(w.won_amount, 0) / NULLIF(q.quota_amount, 0) * 100, 1) AS attainment_pct
FROM finance.quotas q
LEFT JOIN (
    SELECT owner_id, SUM(amount) AS won_amount
    FROM salesforce.opportunity
    WHERE stage_name = 'Closed Won'
      AND close_date >= '2025-01-01'
    GROUP BY owner_id
) w ON q.rep_id = w.owner_id
WHERE q.fiscal_quarter = 'FY26-Q1'
ORDER BY attainment_pct DESC""",
    "Renewal risk": """SELECT
    a.account_name,
    a.industry,
    c.contract_end_date,
    c.arr,
    CASE
        WHEN u.last_login < DATEADD('day', -90, CURRENT_DATE()) THEN 'Inactive'
        WHEN s.nps_score < 7 THEN 'Detractor'
        WHEN c.arr < c.prior_arr THEN 'Downgraded'
        ELSE 'Healthy'
    END AS risk_flag
FROM contracts c
JOIN salesforce.account a ON c.account_id = a.account_id
LEFT JOIN usage_metrics u ON a.account_id = u.account_id
LEFT JOIN surveys s ON a.account_id = s.account_id
  AND s.survey_date = (SELECT MAX(survey_date) FROM surveys WHERE account_id = a.account_id)
WHERE c.contract_end_date BETWEEN CURRENT_DATE() AND DATEADD('day', 90, CURRENT_DATE())
  AND c.status = 'Active'
ORDER BY c.arr DESC""",
}

if "sql_input" not in st.session_state:
    st.session_state.sql_input = ""

sample_options = [""] + list(SAMPLE_QUERIES.keys())
sample = st.selectbox(
    "Try a sample query",
    sample_options,
    format_func=lambda x: "Select a sample..." if x == "" else x,
)
if sample and SAMPLE_QUERIES.get(sample, "") != st.session_state.sql_input:
    st.session_state.sql_input = SAMPLE_QUERIES[sample]
    st.rerun()

sql_input = st.text_area(
    "Paste your SQL here",
    height=250,
    value=st.session_state.sql_input,
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
