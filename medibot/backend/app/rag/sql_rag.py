"""
SQL RAG Chain
==============
Handles structured analytical questions by:
1. Translating natural language to SQL using LLM
2. Cleaning the raw SQL output before execution
3. Executing against mediassist.db
4. Passing results back to LLM for natural language answer
"""
import sqlite3
import re
import logging
from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.rag.hybrid_rag import get_openai

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# DB Schema context (provided to LLM at query time)
# ──────────────────────────────────────────────
DB_SCHEMA = """
Database: mediassist.db

Table: claims
Columns:
  - claim_id (TEXT, primary key): e.g. "CLM-2024-1000"
  - patient_id (TEXT): e.g. "PAT-51347"
  - patient_name (TEXT): patient full name
  - department (TEXT): e.g. "cardiology", "neurology", "nephrology", "orthopaedics", "oncology"
  - claim_type (TEXT): "cashless" or "reimbursement"
  - diagnosis_code (TEXT): ICD code e.g. "I21.4"
  - insurer (TEXT): insurance company name
  - claimed_amount (REAL): amount claimed in INR
  - approved_amount (REAL): amount approved in INR (NULL if pending)
  - status (TEXT): "pending", "approved", "rejected", "escalated"
  - submitted_date (TEXT): ISO date "YYYY-MM-DD"
  - resolved_date (TEXT): ISO date or NULL

Table: maintenance_tickets
Columns:
  - ticket_id (TEXT, primary key): e.g. "TKT-2024-2000"
  - equipment_name (TEXT): equipment model name
  - equipment_id (TEXT): asset ID
  - category (TEXT): e.g. "sterilisation", "infusion", "imaging", "ventilator", "monitor"
  - campus (TEXT): hospital location
  - issue_type (TEXT): "preventive_maintenance", "sensor_failure", "battery_replacement", "calibration", "breakdown"
  - fault_code (TEXT): manufacturer fault code or NULL
  - raised_by (TEXT): staff name
  - raised_date (TEXT): ISO date
  - resolved_date (TEXT): ISO date or NULL
  - status (TEXT): "open", "in_progress", "resolved", "escalated"
  - resolution_note (TEXT): notes on resolution or NULL
"""

SQL_SYSTEM_PROMPT = f"""You are a SQL expert for a healthcare database.
Given the schema below, generate a valid SQLite SQL query for the user's question.
Return ONLY the SQL query — no explanation, no markdown fences, no preamble.

{DB_SCHEMA}"""

ANSWER_SYSTEM_PROMPT = """You are MediBot, an analytical assistant for MediAssist Health Network.
Given a SQL query result, provide a clear, concise natural language answer.
Format numbers clearly (use commas for large numbers, ₹ for currency amounts).
Be professional and specific."""


def clean_sql(raw: str) -> str:
    """
    Strip markdown fences and leading/trailing whitespace from LLM SQL output.
    Handles patterns like:
      ```sql\nSELECT ...\n```
      ```\nSELECT ...\n```
      Just the raw SQL
    """
    # Remove markdown code fences
    cleaned = re.sub(r"```(?:sql)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()
    # Remove any leading explanatory text before SELECT/WITH/INSERT
    match = re.search(r"(SELECT|WITH|INSERT|UPDATE|DELETE|PRAGMA)\b", cleaned, re.IGNORECASE)
    if match:
        cleaned = cleaned[match.start():]
    return cleaned.strip()


def sql_rag_chain(question: str) -> str:
    """
    Plain Python function implementing the 3-step SQL RAG pattern:
    1. LLM → SQL
    2. Clean SQL
    3. Execute SQL → LLM → Natural language answer
    
    Returns: natural language answer string
    """
    client = get_openai()
    db_path = settings.db_path

    # ── Step 1: Natural language → SQL ──
    logger.info(f"SQL RAG: translating question: {question}")
    sql_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.0,
        max_tokens=300,
    )
    raw_sql = sql_response.choices[0].message.content
    logger.info(f"Raw LLM SQL output: {raw_sql}")

    # ── Step 2: Clean the SQL ──
    sql_query = clean_sql(raw_sql)
    logger.info(f"Cleaned SQL: {sql_query}")

    if not sql_query:
        return "I was unable to generate a valid SQL query for your question. Please rephrase it."

    # ── Step 3: Execute SQL ──
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            result_text = "The query returned no results."
        else:
            # Format as readable text
            col_names = rows[0].keys() if rows else []
            result_lines = [" | ".join(str(col_names[i]) for i in range(len(col_names)))]
            result_lines.append("-" * 60)
            for row in rows[:50]:  # Cap at 50 rows
                result_lines.append(" | ".join(str(row[i]) for i in range(len(row))))
            if len(rows) > 50:
                result_lines.append(f"... and {len(rows) - 50} more rows")
            result_text = "\n".join(result_lines)

        logger.info(f"SQL returned {len(rows)} rows")

    except sqlite3.Error as e:
        logger.error(f"SQL execution error: {e} | Query: {sql_query}")
        return f"I encountered an error executing the query: {str(e)}. Please rephrase your question."

    # ── Step 4: LLM interprets SQL result ──
    answer_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"SQL Query used: {sql_query}\n\n"
                    f"Query Result:\n{result_text}\n\n"
                    f"Provide a clear natural language answer."
                ),
            },
        ],
        temperature=0.1,
        max_tokens=500,
    )
    return answer_response.choices[0].message.content
