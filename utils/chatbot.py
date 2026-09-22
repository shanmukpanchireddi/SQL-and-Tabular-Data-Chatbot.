import os
import re
import time
import logging
from typing import List, Tuple, Any
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from utils.load_config import LoadConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

APPCFG = LoadConfig()

SQL_PROMPT = PromptTemplate(
    input_variables=["input", "top_k", "dialect", "table_info"],
    template="""You are a {dialect} expert. Given an input question, create a syntactically correct {dialect} query to run.
Unless the user specifies a specific number of examples to obtain, limit your query to at most {top_k} results.
Never query for all columns from a table. Only ask for the relevant columns given the question.

Table Schema:
{table_info}

Rules:
1. Output ONLY the raw SQL query. Do not wrap in markdown code blocks or add preambles.
2. For queries asking for distinct values of a column (e.g. "distinct genres values" or "distinct column values"), return standard SQL:
   SELECT COUNT(DISTINCT column_name) FROM table_name;
3. For queries asking for individual items stored as pipe-separated '|' values in a text column (e.g. "individual genres"), use a SQLite WITH RECURSIVE CTE:
   WITH RECURSIVE split(col_item, rest) AS (
     SELECT
       CASE WHEN instr(col, '|') > 0 THEN substr(col, 1, instr(col, '|') - 1) ELSE col END,
       CASE WHEN instr(col, '|') > 0 THEN substr(col, instr(col, '|') + 1) ELSE '' END
     FROM table_name
     UNION ALL
     SELECT
       CASE WHEN instr(rest, '|') > 0 THEN substr(rest, 1, instr(rest, '|') - 1) ELSE rest END,
       CASE WHEN instr(rest, '|') > 0 THEN substr(rest, instr(rest, '|') + 1) ELSE '' END
     FROM split
     WHERE rest <> ''
   )
   SELECT COUNT(DISTINCT col_item) FROM split WHERE col_item <> '' AND col_item IS NOT NULL;

Question: {input}
SQLQuery:"""
)

ANSWER_PROMPT_TEMPLATE = """You are an AI data assistant. Provide a helpful, clear, and direct answer to the user's question based strictly on the provided SQL query and SQL execution result.

User Question: {question}
Executed SQL: {query}
SQL Execution Result: {result}

Rules:
- Answer the user's question directly and concisely based ONLY on the SQL result.
- If the result contains tabular data, summarize key metrics or present the data clearly.
- If the result is a single number or text, state it directly.
- Do not mention SQL query details or internal syntax unless asked.
- Never invent information not contained in the SQL result.
Answer:"""

def invoke_with_retry(runnable: Any, input_data: dict, max_retries: int = 3) -> Any:
    """Invoke runnable chain with automatic backoff retry for rate limits and transient connection errors."""
    for attempt in range(max_retries):
        try:
            return runnable.invoke(input_data)
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(k in err_str for k in ["rate limit", "429", "rate_limit", "connection error", "getaddrinfo failed", "connecterror"])
            if is_transient and attempt < max_retries - 1:
                sleep_sec = 2 * (attempt + 1)
                logger.warning(f"Transient error ({e}). Retrying in {sleep_sec}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(sleep_sec)
            else:
                raise e

def clean_sql_query(query: str) -> str:
    """Extract and clean raw SQL statement from LLM output."""
    if not query:
        return ""
    
    # 1. Extract content inside markdown code blocks
    markdown_match = re.search(r"```(?:sql)?\s*(.*?)\s*```", query, flags=re.DOTALL | re.IGNORECASE)
    if markdown_match:
        query = markdown_match.group(1)

    # 2. Extract content after SQLQuery / Query labels
    sql_label_match = re.search(r"(?:SQLQuery|SQL Query|Query|SQL):\s*(.*)", query, flags=re.DOTALL | re.IGNORECASE)
    if sql_label_match:
        query = sql_label_match.group(1)

    # 3. Match SQL starting keywords (WITH, SELECT, PRAGMA, EXPLAIN)
    select_match = re.search(r"\b(WITH|SELECT|PRAGMA|EXPLAIN)\b.*", query, flags=re.DOTALL | re.IGNORECASE)
    if select_match:
        query = select_match.group(0)

    # 4. Remove trailing semicolons
    if ";" in query:
        query = query.split(";")[0]

    return query.strip()

def validate_sql_query(query: str) -> bool:
    """Validate that the query is non-empty and read-only."""
    if not query:
        raise ValueError("Generated SQL query is empty.")
    
    upper_query = query.strip().upper()
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "CREATE"]
    for word in forbidden:
        if re.search(r"\b" + word + r"\b", upper_query):
            raise ValueError(f"DML operation '{word}' is not permitted.")

    allowed_starts = ("SELECT", "WITH", "PRAGMA", "EXPLAIN")
    if not any(upper_query.startswith(kw) for kw in allowed_starts):
        raise ValueError(f"Invalid SQL: query must begin with SELECT or WITH. Got: '{query[:30]}...'")
    
    return True

def execute_sql_with_sqlalchemy(db: SQLDatabase, query: str) -> List[Tuple]:
    """Execute raw SQL query using SQLAlchemy connection."""
    engine = db._engine
    with engine.connect() as connection:
        result_proxy = connection.execute(text(query))
        if result_proxy.returns_rows:
            rows = result_proxy.fetchall()
            return [tuple(row) for row in rows]
        return []

def clean_error_message(err: Exception) -> str:
    """Format SQLAlchemy & SQLite error messages into clean user-facing strings."""
    err_msg = str(err)
    err_msg = re.sub(r'\(Background on this error at:.*?\)', '', err_msg, flags=re.DOTALL)
    err_msg = re.sub(r'\[SQL:.*?\]', '', err_msg, flags=re.DOTALL)
    err_msg = re.sub(r'\(sqlite3\.OperationalError\)\s*', '', err_msg)
    err_msg = re.sub(r'Error code: 429 - .*?Please try again in [\d\.]+s\.', 'API Rate limit encountered. Please try again in a few seconds.', err_msg, flags=re.DOTALL)
    return err_msg.strip()

def generate_and_execute_sql(write_query_chain: Any, db: SQLDatabase, question: str) -> Tuple[str, List[Tuple]]:
    """Generate SQL, clean, validate, and execute with single retry logic."""
    first_error = None
    try:
        raw_query = invoke_with_retry(write_query_chain, {"question": question})
        sql_query = clean_sql_query(str(raw_query))
        validate_sql_query(sql_query)
        logger.info(f"Generated SQL: {sql_query}")
        
        result = execute_sql_with_sqlalchemy(db, sql_query)
        logger.info(f"SQL Result: {result[:5]} (total {len(result)} rows)")
        return sql_query, result
    except Exception as e1:
        first_error = e1
        logger.warning(f"First SQL execution attempt failed: {e1}. Retrying...")
        try:
            retry_question = f"{question} (Note: previous SQL attempt failed: {clean_error_message(e1)}. Output valid SELECT or WITH query using exact table and column names)."
            raw_query = invoke_with_retry(write_query_chain, {"question": retry_question})
            sql_query = clean_sql_query(str(raw_query))
            validate_sql_query(sql_query)
            logger.info(f"Regenerated SQL (Attempt 2): {sql_query}")
            
            result = execute_sql_with_sqlalchemy(db, sql_query)
            logger.info(f"SQL Result (Attempt 2): {result[:5]}")
            return sql_query, result
        except Exception as e2:
            logger.error(f"Second SQL attempt failed: {e2}")
            err_to_report = first_error if ("no such table" in str(first_error) or "no such column" in str(first_error)) else e2
            cleaned_err = clean_error_message(err_to_report)
            raise RuntimeError(cleaned_err)

class ChatBot:
    @staticmethod
    def respond(chatbot: List, message: str, chat_type: str, app_functionality: str) -> Tuple[str, List]:
        if not message or not message.strip():
            return "", chatbot

        chatbot = chatbot or []

        if app_functionality == "Chat":
            db_path = None
            missing_db_error = ""

            if chat_type == "Q&A with stored SQL-DB":
                db_path = APPCFG.sqldb_directory
                missing_db_error = "SQL DB does not exist. Please check 'data/sqldb.db'."
            elif chat_type == "Q&A with Uploaded CSV/XLSX SQL-DB":
                db_path = APPCFG.uploaded_files_sqldb_directory
                missing_db_error = "SQL DB for uploaded CSV/XLSX files does not exist. Please upload a CSV/XLSX file first."
            elif chat_type == "Q&A with stored CSV/XLSX SQL-DB":
                db_path = APPCFG.stored_csv_xlsx_sqldb_directory
                missing_db_error = "SQL DB for stored CSV/XLSX files does not exist. Please run `prepare_csv_xlsx_sqlitedb.py` first."
            elif chat_type == "RAG with stored CSV/XLSX ChromaDB":
                try:
                    collection = APPCFG.chroma_client.get_collection(name=APPCFG.collection_name)
                    results = collection.query(query_texts=[message], n_results=APPCFG.top_k)
                    docs = results.get("documents", [[]])[0]
                    context = "\n".join(docs) if docs else "No matching documents found."
                    
                    answer_prompt = PromptTemplate.from_template(
                        "Question: {question}\nSearch Context:\n{context}\nAnswer the question concisely based on the context:"
                    )
                    chain = answer_prompt | APPCFG.groq_llm | StrOutputParser()
                    response = invoke_with_retry(chain, {"question": message, "context": context})
                    chatbot.append((message, response))
                    return "", chatbot
                except Exception as e:
                    logger.error(f"ChromaDB RAG query error: {e}")
                    chatbot.append((message, f"Vector DB search failed: {clean_error_message(e)}. Make sure to run prepare_csv_xlsx_vectordb.py first."))
                    return "", chatbot
            else:
                return "", chatbot

            if not db_path or not os.path.exists(db_path):
                chatbot.append((message, missing_db_error))
                return "", chatbot

            try:
                engine = create_engine(f"sqlite:///{db_path}")
                db = SQLDatabase(engine=engine)

                table_names = db.get_usable_table_names()
                if not table_names:
                    chatbot.append((message, "The database is currently empty. Please upload data or populate tables first."))
                    return "", chatbot

                write_query = create_sql_query_chain(APPCFG.groq_llm, db, prompt=SQL_PROMPT)

                history_context = ""
                if len(chatbot) > 0:
                    recent_turns = []
                    for u, b in chatbot[-3:]:
                        if u and b and u != "Uploaded File(s)":
                            recent_turns.append(f"User: {u}\nAssistant: {b}")
                    if recent_turns:
                        history_context = "Previous conversation:\n" + "\n".join(recent_turns) + "\n\nCurrent Question: "

                query_input = f"{history_context}{message}" if history_context else message

                sql_query, sql_result = generate_and_execute_sql(write_query, db, query_input)

                if not sql_result:
                    response = "No matching records found."
                elif len(sql_result) == 1 and len(sql_result[0]) == 1 and sql_result[0][0] is not None:
                    val = str(sql_result[0][0])
                    response = f"Result: **{val}**"
                else:
                    answer_prompt = PromptTemplate.from_template(ANSWER_PROMPT_TEMPLATE)
                    answer_chain = answer_prompt | APPCFG.groq_llm | StrOutputParser()
                    
                    formatted_result = str(sql_result[:20])
                    response = invoke_with_retry(answer_chain, {
                        "question": message,
                        "query": sql_query,
                        "result": formatted_result
                    })

                chatbot.append((message, response))
                return "", chatbot

            except Exception as e:
                logger.error(f"Chatbot execution error: {e}", exc_info=True)
                clean_err = clean_error_message(e)
                chatbot.append((message, f"Query Error: {clean_err}"))
                return "", chatbot

        return "", chatbot
