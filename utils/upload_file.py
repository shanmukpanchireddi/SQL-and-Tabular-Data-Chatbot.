import os
import re
from typing import List, Tuple, Union, Any
from utils.load_config import LoadConfig
from sqlalchemy import create_engine, inspect, text
import pandas as pd

APPCFG = LoadConfig()

def sanitize_identifier(name: str, default_prefix: str = "col") -> str:
    """Sanitize table or column names to be valid SQLite identifiers."""
    name = str(name).strip()
    # Replace whitespace, dots, hyphens, and slashes with underscores
    name = re.sub(r'[\s\-\.\/]+', '_', name)
    # Remove all non-alphanumeric and non-underscore characters
    name = re.sub(r'[^\w]', '', name)
    # If empty or starts with a digit, prefix
    if not name:
        name = f"{default_prefix}_1"
    elif name[0].isdigit():
        name = f"{default_prefix}_{name}"
    return name

class ProcessFiles:
    def __init__(self, files_dir: Union[List, Any], chatbot: List) -> None:
        self.files_dir = files_dir if isinstance(files_dir, list) else [files_dir]
        self.chatbot = chatbot or []
        db_path = APPCFG.uploaded_files_sqldb_directory
        db_uri = f"sqlite:///{db_path}"
        self.engine = create_engine(db_uri)

        # Safe dataset reset: drop all existing tables to prevent cross-contamination
        try:
            insp = inspect(self.engine)
            existing_tables = insp.get_table_names()
            if existing_tables:
                with self.engine.connect() as conn:
                    for tbl in existing_tables:
                        conn.execute(text(f'DROP TABLE IF EXISTS "{tbl}"'))
                    conn.commit()
        except Exception as e:
            print(f"Notice during reset: {e}")

    def _process_uploaded_files(self) -> Tuple[str, List]:
        if not self.files_dir:
            self.chatbot.append(("", "No files were selected for upload."))
            return "", self.chatbot

        created_tables = []
        for file_item in self.files_dir:
            if not file_item:
                continue
            
            if hasattr(file_item, 'name'):
                file_path = file_item.name
                orig_name = getattr(file_item, 'orig_name', os.path.basename(file_path))
            elif isinstance(file_item, dict) and 'name' in file_item:
                file_path = file_item['name']
                orig_name = file_item.get('orig_name', os.path.basename(file_path))
            else:
                file_path = str(file_item)
                orig_name = os.path.basename(file_path)

            if not os.path.exists(file_path):
                continue

            raw_name, file_extension = os.path.splitext(orig_name)
            table_name = sanitize_identifier(raw_name, default_prefix="tbl")

            try:
                if file_extension.lower() == ".csv":
                    df = pd.read_csv(file_path)
                elif file_extension.lower() in [".xlsx", ".xls"]:
                    df = pd.read_excel(file_path)
                else:
                    self.chatbot.append(("", f"File '{orig_name}' has an unsupported file format ({file_extension}). Allowed: .csv, .xlsx"))
                    continue

                if df.empty:
                    self.chatbot.append(("", f"Uploaded file '{orig_name}' is empty."))
                    continue

                # Sanitize column headers
                sanitized_cols = {}
                seen_cols = set()
                for col in df.columns:
                    clean_col = sanitize_identifier(str(col), default_prefix="col")
                    counter = 1
                    col_candidate = clean_col
                    while col_candidate in seen_cols:
                        col_candidate = f"{clean_col}_{counter}"
                        counter += 1
                    seen_cols.add(col_candidate)
                    sanitized_cols[col] = col_candidate

                df = df.rename(columns=sanitized_cols)

                # Write cleanly to SQLite
                df.to_sql(table_name, self.engine, if_exists='replace', index=False)
                created_tables.append(table_name)
            except Exception as e:
                print(f"Error processing file {orig_name}: {e}")
                self.chatbot.append(("", f"Failed to process file '{orig_name}': {str(e)}"))

        if created_tables:
            table_str = ", ".join([f"'{t}'" for t in created_tables])
            msg = f"Uploaded files processed successfully! Table(s) created in database: {table_str}. Ask your question below!"
            self.chatbot.append(("Uploaded File(s)", msg))
        else:
            self.chatbot.append(("Uploaded File(s)", "No valid tables could be created from the uploaded files."))

        return "", self.chatbot

    def _validate_db(self):
        try:
            insp = inspect(self.engine)
            table_names = insp.get_table_names()
            print("==============================")
            print("Available tables in uploaded SQL DB:", table_names)
            print("==============================")
        except Exception as e:
            print("Validation error:", e)

    def run(self) -> Tuple[str, List]:
        input_txt, chatbot = self._process_uploaded_files()
        self._validate_db()
        return input_txt, chatbot

class UploadFile:
    @staticmethod
    def run_pipeline(files_dir: Union[List, Any], chatbot: List, chatbot_functionality: str) -> Tuple[str, List]:
        pipeline_instance = ProcessFiles(files_dir=files_dir, chatbot=chatbot)
        input_txt, chatbot = pipeline_instance.run()
        return input_txt, chatbot