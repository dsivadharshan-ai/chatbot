import streamlit as st
import pandas as pd
import pyodbc

@st.cache_resource
def get_connection():
    return pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};'
        'SERVER=srv-ino-db01;'
        'DATABASE=address_tool_ai_dev;'
        'Trusted_Connection=yes;'
        'TrustServerCertificate=yes;'
    )

conn = get_connection()


st.title("dbo Table Explorer + Duplicate Detection")

tables = pd.read_sql("""
    SELECT TABLE_NAME 
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA='dbo'
    ORDER BY TABLE_NAME
""", conn)

# Exclude ikav and ikavios tables from selection list
filtered_tables = tables[~tables['TABLE_NAME'].str.contains(r'ikav|ikavios', case=False)]

table_name = st.selectbox("Choose a dbo table", filtered_tables["TABLE_NAME"].tolist())

if table_name:
    st.subheader(f"Table: dbo.{table_name}")

    df = pd.read_sql(f"SELECT * FROM dbo.{table_name}", conn)

    st.metric("Row count", len(df))
    st.metric("Column count", len(df.columns))
    st.write("Columns:", df.columns.tolist())

    if st.checkbox("Show top rows (head)"):
        st.dataframe(df.head(20))

    uniq_cols = [c for c in df.columns if df[c].nunique() == len(df)]
    st.write("Unique-key candidates:", uniq_cols or "none found")

    st.subheader("Unique values per column (with nulls)")
    for col in df.columns:
        null_count = df[col].isna().sum()
        values = df[col].dropna().unique()
        max_items = 20
        show_values = values[:max_items]
        st.write(f"**{col}** ({len(values)} unique values, {null_count} nulls):", show_values.tolist())
        if len(values) > max_items:
            st.write(f"... plus {len(values) - max_items} more values")

    dup_all = df[df.duplicated(keep=False)]
    st.metric("Full-row duplicates", len(dup_all))
    if len(dup_all) > 0:
        st.write("Full-row duplicates (sample):")
        st.dataframe(dup_all.head(20))

    st.subheader("Find duplicates by key columns")
    default_cols = [c for c in df.columns if c.lower() in ["name", "firstname", "lastname", "postcode", "postalcode", "city"]]
    key_cols = st.multiselect(
        "Choose columns that define a duplicate group",
        df.columns.tolist(),
        default=default_cols[:2] if len(default_cols) > 1 else default_cols
    )
    if key_cols:
        dup_by = df[df.duplicated(subset=key_cols, keep=False)]
        st.metric("Key-based duplicates", len(dup_by))
        if len(dup_by) > 0:
            st.write(f"Duplicate rows by {', '.join(key_cols)} (showing first 100):")
            st.dataframe(dup_by.sort_values(by=key_cols).head(100))
        else:
            st.write("No duplicates found using selected key columns.")

    if st.button("Export current report"):
        report = {
            "table_name": table_name,
            "row_count": len(df),
            "col_count": len(df.columns),
            "full_duplicates": len(dup_all),
            "unique_key_candidates": ",".join(uniq_cols),
        }
        report_df = pd.DataFrame([report])
        result_csv = report_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download report CSV",
            result_csv,
            f"table_audit_{table_name}.csv",
            "text/csv",
        )



        