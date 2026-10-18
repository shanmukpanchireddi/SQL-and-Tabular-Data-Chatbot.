
import os
import re
from typing import Any, List, Tuple, Union

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from utils.load_config import LoadConfig


APPCFG = LoadConfig()


def sanitize_identifier(name: str, default_prefix: str = "col") -> str:
    """Convert table and column names into safe SQLite identifiers."""
    name = str(name).strip()

    # Replace spaces and common separators with underscores.
    name = re.sub(r"[\s./\\-]+", "_", name)

    # Keep only letters, digits, and underscores.
    name = re.sub(r"[^\w]", "", name)

    if not name:
        name = f"{default_prefix}_1"
    elif name[0].isdigit():
        name = f"{default_prefix}_{name}"

    return name


def add_message(history: list, role: str, content: str) -> None:
    """Append a message in Gradio's dictionary message format."""
    history.append(
        {
            "role": role,
            "content": str(content),
        }
    )


class ProcessFiles:
    def __init__(
        self,
        files_dir: Union[List, Any],
        chatbot: List,
    ) -> None:
        self.files_dir = (
            files_dir if isinstance(files_dir, list) else [files_dir]
        )
        self.chatbot = list(chatbot or [])

        db_path = APPCFG.uploaded_files_sqldb_directory
        os.makedirs(
            os.path.dirname(os.path.abspath(db_path)),
            exist_ok=True,
        )

        self.engine = create_engine(f"sqlite:///{db_path}")

        # Clear old uploaded tables so they are not mixed with new data.
        try:
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            if existing_tables:
                with self.engine.begin() as connection:
                    for table_name in existing_tables:
                        safe_name = table_name.replace('"', '""')
                        connection.execute(
                            text(f'DROP TABLE IF EXISTS "{safe_name}"')
                        )

        except Exception as exc:
            print(f"Notice during database reset: {exc}")

    def _process_uploaded_files(self) -> Tuple[str, List]:
        if not self.files_dir or not any(self.files_dir):
            add_message(
                self.chatbot,
                "assistant",
                "No files were selected for upload.",
            )
            return "", self.chatbot

        created_tables = []

        for file_item in self.files_dir:
            if not file_item:
                continue

            # Support Gradio file objects and file dictionaries.
            if hasattr(file_item, "name"):
                file_path = file_item.name
                original_name = getattr(
                    file_item,
                    "orig_name",
                    os.path.basename(file_path),
                )
            elif isinstance(file_item, dict) and "name" in file_item:
                file_path = file_item["name"]
                original_name = file_item.get(
                    "orig_name",
                    os.path.basename(file_path),
                )
            else:
                file_path = str(file_item)
                original_name = os.path.basename(file_path)

            if not os.path.exists(file_path):
                add_message(
                    self.chatbot,
                    "assistant",
                    f"File not found: {original_name}",
                )
                continue

            raw_name, extension = os.path.splitext(original_name)
            table_name = sanitize_identifier(
                raw_name,
                default_prefix="tbl",
            )

            try:
                if extension.lower() == ".csv":
                    dataframe = pd.read_csv(file_path)

                elif extension.lower() in (".xlsx", ".xls"):
                    dataframe = pd.read_excel(file_path)

                else:
                    add_message(
                        self.chatbot,
                        "assistant",
                        f"Unsupported file format for {original_name}. "
                        "Please upload a CSV or Excel file.",
                    )
                    continue

                if dataframe.empty:
                    add_message(
                        self.chatbot,
                        "assistant",
                        f"The uploaded file {original_name} is empty.",
                    )
                    continue

                # Clean column names and make duplicates unique.
                sanitized_columns = {}
                seen_columns = set()

                for column in dataframe.columns:
                    clean_column = sanitize_identifier(
                        str(column),
                        default_prefix="col",
                    )
                    candidate = clean_column
                    counter = 1

                    while candidate in seen_columns:
                        candidate = f"{clean_column}_{counter}"
                        counter += 1

                    seen_columns.add(candidate)
                    sanitized_columns[column] = candidate

                dataframe = dataframe.rename(
                    columns=sanitized_columns
                )

                dataframe.to_sql(
                    table_name,
                    self.engine,
                    if_exists="replace",
                    index=False,
                )

                created_tables.append(table_name)

            except Exception as exc:
                print(
                    f"Error processing file {original_name}: {exc}"
                )
                add_message(
                    self.chatbot,
                    "assistant",
                    f"Failed to process {original_name}: {exc}",
                )

        if created_tables:
            tables_text = ", ".join(
                f"'{name}'" for name in created_tables
            )
            message = (
                "Upload successful! Created database table(s): "
                f"{tables_text}. You can now ask questions about your data."
            )
        else:
            message = (
                "No valid tables were created. "
                "Please check your uploaded files."
            )

        add_message(self.chatbot, "assistant", message)

        return "", self.chatbot

    def _validate_db(self) -> None:
        try:
            table_names = inspect(self.engine).get_table_names()

            print("==============================")
            print(
                "Available tables in uploaded SQL DB:",
                table_names,
            )
            print("==============================")

        except Exception as exc:
            print("Database validation error:", exc)

    def run(self) -> Tuple[str, List]:
        try:
            input_text, chatbot = self._process_uploaded_files()
            self._validate_db()
            return input_text, chatbot
        finally:
            self.engine.dispose()


class UploadFile:
    @staticmethod
    def run_pipeline(
        files_dir: Union[List, Any],
        chatbot: List,
        chatbot_functionality: str,
    ) -> Tuple[str, List]:
        pipeline = ProcessFiles(
            files_dir=files_dir,
            chatbot=chatbot,
        )
        return pipeline.run()
