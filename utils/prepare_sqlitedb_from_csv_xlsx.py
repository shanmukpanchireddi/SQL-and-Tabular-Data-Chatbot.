import os
import re
import pandas as pd
from sqlalchemy import create_engine, inspect
from utils.load_config import LoadConfig

def sanitize_identifier(name: str, default_prefix: str = "col") -> str:
    name = str(name).strip()
    name = re.sub(r'[\s\-\.\/]+', '_', name)
    name = re.sub(r'[^\w]', '', name)
    if not name:
        name = f"{default_prefix}_1"
    elif name[0].isdigit():
        name = f"{default_prefix}_{name}"
    return name

class PrepareSQLFromTabularData:
    def __init__(self, files_dir: str) -> None:
        APPCFG = LoadConfig()
        self.files_directory = files_dir
        self.file_dir_list = [f for f in os.listdir(files_dir) if not f.startswith('.')]
        db_path = APPCFG.stored_csv_xlsx_sqldb_directory
        db_uri = f"sqlite:///{db_path}"
        self.engine = create_engine(db_uri)
        print("Number of stored files found:", len(self.file_dir_list))

    def _prepare_db(self):
        for file in self.file_dir_list:
            full_file_path = os.path.join(self.files_directory, file)
            raw_name, file_extension = os.path.splitext(file)
            table_name = sanitize_identifier(raw_name, default_prefix="tbl")

            if file_extension.lower() == ".csv":
                df = pd.read_csv(full_file_path)
            elif file_extension.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(full_file_path)
            else:
                print(f"Skipping unsupported file: {file}")
                continue

            # Sanitize columns
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
            df.to_sql(table_name, self.engine, if_exists='replace', index=False)
            print(f"Table '{table_name}' saved to SQL DB from {file}")

        print("==============================")
        print("All stored CSV/XLSX files are saved into the SQL database.")

    def _validate_db(self):
        insp = inspect(self.engine)
        table_names = insp.get_table_names()
        print("==============================")
        print("Available table names in created SQL DB:", table_names)
        print("==============================")

    def run_pipeline(self):
        self._prepare_db()
        self._validate_db()
