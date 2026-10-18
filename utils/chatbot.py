
import os
import re
import time
import logging
from typing import Any, List, Tuple

from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from utils.load_config import LoadConfig


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

APPCFG = LoadConfig()


SQL_PROMPT = PromptTemplate(
    input_variables=["input", "top_k", "dialect", "table_info"],
    template="""You are a {dialect} expert. Given a question, create a
syntactically correct, read-only SQL query.

Unless the user specifies a number of examples, limit results to {top_k}.
Never select all columns unless necessary. Use the exact table and column
names provided in the schema.

Schema:
{table_info}

Rules:
1. Output only the SQL query.
2. Use SELECT or WITH queries only.
3. For questions asking how many distinct values exist in a column,
   use COUNT(DISTINCT column_name).
4. For pipe-separated values in SQLite text columns, use a recursive CTE
   when individual values need to be counted.

Question: {input}
SQLQuery:""",
)


ANSWER_PROMPT_TEMPLATE = """You are an AI data assistant.

Answer the user's question using only the supplied SQL result.

Question: {question}
SQL query: {query}
SQL result: {result}

Give a clear, concise answer. Do not invent information.
Answer:"""


def invoke_with_retry(
    runnable: Any,
    input_data: dict,
    max_retries: int = 3,
) -> Any:
    for attempt in range(max_retries):
        try:
            return runnable.invoke(input_data)
        except Exception as exc:
            error_text = str(exc).lower()
            transient = any(
                term in error_text
                for term in (
                    "rate limit",
                    "429",
                    "connection error",
                    "connecterror",
                    "getaddrinfo failed",
                    "timeout",
                )
            )

            if not transient or attempt == max_retries - 1:
                raise

            delay = 2 * (attempt + 1)
            logger.warning(
                "Temporary API/network error. Retrying in %s seconds.",
                delay,
            )
            time.sleep(delay)

    raise RuntimeError("The request failed after multiple attempts.")


def clean_sql_query(query: str) -> str:
    if not query:
        return ""

    query = query.strip()

    match = re.search(
        r"```(?:sql)?\s*(.*?)```",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        query = match.group(1).strip()

    query = re.sub(
        r"^\s*(?:SQLQuery|SQL Query|Query|SQL)\s*:\s*",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip()

    match = re.search(
        r"\b(WITH|SELECT|PRAGMA|EXPLAIN)\b.*",
        query,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        query = match.group(0).strip()

    # Remove a trailing semicolon without truncating SQL inside a statement.
    query = query.rstrip().rstrip(";").strip()
    return query


def validate_sql_query(query: str) -> bool:
    if not query:
        raise ValueError("The generated SQL query is empty.")

    cleaned = query.strip()

    # Only permit read-only query forms.
    if not re.match(
        r"^(SELECT|WITH|PRAGMA|EXPLAIN)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        raise ValueError("Only read-only SQL queries are permitted.")

    # Block multiple statements and write operations.
    if ";" in cleaned:
        raise ValueError("Multiple SQL statements are not permitted.")

    if re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|"
        r"ATTACH|DETACH|VACUUM|REINDEX)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        raise ValueError("A write or database-modification operation was blocked.")

    return True


def execute_sql_with_sqlalchemy(
    db: SQLDatabase,
    query: str,
) -> List[Tuple]:
    validate_sql_query(query)

    with db._engine.connect() as connection:
        result = connection.execute(text(query))

        if result.returns_rows:
            return [tuple(row) for row in result.fetchall()]

    return []


def clean_error_message(err: Exception) -> str:
    message = str(err)

    if "429" in message or "rate limit" in message.lower():
        return "The AI service rate limit was reached. Please wait and try again."

    if "no such table" in message.lower():
        return (
            "The requested table was not found in the selected database. "
            "Check that the correct file and table were uploaded."
        )

    if "no such column" in message.lower():
        return (
            "A requested column was not found. Please check the uploaded "
            "file's column names and try asking the question again."
        )

    return message[:1000]


def generate_and_execute_sql(
    write_query_chain: Any,
    db: SQLDatabase,
    question: str,
) -> Tuple[str, List[Tuple]]:
    first_error = None

    for attempt in range(2):
        try:
            current_question = question

            if attempt == 1 and first_error:
                current_question = (
                    f"{question}\nThe previous attempt failed with: "
                    f"{clean_error_message(first_error)}. "
                    "Use the exact schema and generate a valid read-only query."
                )

            raw_query = invoke_with_retry(
                write_query_chain,
                {"question": current_question},
            )

            sql_query = clean_sql_query(str(raw_query))
            validate_sql_query(sql_query)

            logger.info("Generated SQL: %s", sql_query)

            result = execute_sql_with_sqlalchemy(db, sql_query)
            logger.info("SQL returned %s rows.", len(result))

            return sql_query, result

        except Exception as exc:
            if attempt == 0:
                first_error = exc
                logger.warning("First SQL attempt failed: %s", exc)
            else:
                raise RuntimeError(clean_error_message(exc)) from exc

    raise RuntimeError(clean_error_message(first_error))


def add_message(history: List[dict], role: str, content: str) -> None:
    """Append a message in the format expected by Gradio 6."""
    history.append({"role": role, "content": str(content)})


def history_to_text(history: List[dict]) -> str:
    """Convert recent Gradio messages into context for SQL questions."""
    recent = []

    for item in history[-6:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role", "")
        content = item.get("content", "")

        if not isinstance(content, str) or not content.strip():
            continue

        if role == "user":
            recent.append(f"User: {content}")
        elif role == "assistant":
            recent.append(f"Assistant: {content}")

    return "\n".join(recent)


class ChatBot:
    @staticmethod
    def respond(
        chatbot: List,
        message: str,
        chat_type: str,
        app_functionality: str,
    ) -> Tuple[str, List[dict]]:
        history = list(chatbot or [])

        if not message or not message.strip():
            return "", history

        question = message.strip()

        # This project currently implements chat-based SQL and RAG.
                # Allow supported app functionality modes.
        if app_functionality not in ("Chat", "Process files"):
            add_message(history, "user", question)
            add_message(
                history,
                "assistant",
                "Please select Chat or Process files to continue.",
            )
            return "", history

        if chat_type == "RAG with stored CSV/XLSX ChromaDB":
            try:
                collection = APPCFG.chroma_client.get_collection(
                    name=APPCFG.collection_name
                )

                results = collection.query(
                    query_texts=[question],
                    n_results=APPCFG.top_k,
                )

                documents = results.get("documents", [[]])[0]
                context = (
                    "\n".join(documents)
                    if documents
                    else "No matching documents found."
                )

                prompt = PromptTemplate.from_template(
                    "Question: {question}\n"
                    "Search context:\n{context}\n"
                    "Answer clearly using the context. "
                    "If the context does not contain the answer, say so."
                )

                chain = prompt | APPCFG.groq_llm | StrOutputParser()

                response = invoke_with_retry(
                    chain,
                    {"question": question, "context": context},
                )

            except Exception as exc:
                logger.exception("ChromaDB query failed")
                response = (
                    "Document search failed: "
                    + clean_error_message(exc)
                    + ". Check that the document index has been prepared."
                )

            add_message(history, "user", question)
            add_message(history, "assistant", response)
            return "", history

        database_paths = {
            "Q&A with stored SQL-DB": (
                APPCFG.sqldb_directory,
                "The stored SQL database was not found.",
            ),
            "Q&A with Uploaded CSV/XLSX SQL-DB": (
                APPCFG.uploaded_files_sqldb_directory,
                "The uploaded CSV/XLSX database was not found. Upload a file first.",
            ),
            "Q&A with stored CSV/XLSX SQL-DB": (
                APPCFG.stored_csv_xlsx_sqldb_directory,
                "The stored CSV/XLSX database was not found. Prepare the database first.",
            ),
        }

        if chat_type not in database_paths:
            add_message(history, "user", question)
            add_message(
                history,
                "assistant",
                "Please select a supported chat mode.",
            )
            return "", history

        db_path, missing_message = database_paths[chat_type]

        if not db_path or not os.path.exists(db_path):
            add_message(history, "user", question)
            add_message(history, "assistant", missing_message)
            return "", history

        try:
            engine = create_engine(f"sqlite:///{db_path}")

            try:
                db = SQLDatabase(engine=engine)

                table_names = db.get_usable_table_names()
                logger.info("Available SQL tables: %s", table_names)

                if not table_names:
                    response = "The selected database contains no usable tables."
                else:
                    write_query = create_sql_query_chain(
                        APPCFG.groq_llm,
                        db,
                        prompt=SQL_PROMPT,
                    )

                    previous_context = history_to_text(history)
                    query_input = question

                    if previous_context:
                        query_input = (
                            f"Previous conversation:\n{previous_context}\n\n"
                            f"Current question: {question}"
                        )

                    sql_query, sql_result = generate_and_execute_sql(
                        write_query,
                        db,
                        query_input,
                    )

                    if not sql_result:
                        response = "No matching records were found."

                    elif (
                        len(sql_result) == 1
                        and len(sql_result[0]) == 1
                    ):
                        response = f"Result: {sql_result[0][0]}"

                    else:
                        answer_prompt = PromptTemplate.from_template(
                            ANSWER_PROMPT_TEMPLATE
                        )
                        answer_chain = (
                            answer_prompt
                            | APPCFG.groq_llm
                            | StrOutputParser()
                        )

                        response = invoke_with_retry(
                            answer_chain,
                            {
                                "question": question,
                                "query": sql_query,
                                "result": str(sql_result[:20]),
                            },
                        )

            finally:
                engine.dispose()

        except Exception as exc:
            logger.exception("Chatbot SQL execution failed")
            response = "Query error: " + clean_error_message(exc)

        add_message(history, "user", question)
        add_message(history, "assistant", response)

        return "", history
