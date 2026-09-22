import os
import yaml
import shutil
import chromadb
from dotenv import load_dotenv
from pyprojroot import here
from langchain_groq import ChatGroq

# Load environment variables from .env files
load_dotenv(here(".env"))
if os.path.exists(here("utils/.env")):
    load_dotenv(here("utils/.env"))

class LoadConfig:
    def __init__(self) -> None:
        config_path = here("configs/app_config.yml")
        with open(config_path, "r", encoding="utf-8") as cfg:
            app_config = yaml.load(cfg, Loader=yaml.FullLoader)

        self.load_directories(app_config=app_config)
        self.load_llm_configs(app_config=app_config)
        self.load_models()
        self.load_chroma_client()
        self.load_rag_config(app_config=app_config)

    def load_directories(self, app_config: dict):
        self.stored_csv_xlsx_directory = str(here(app_config["directories"]["stored_csv_xlsx_directory"]))
        self.sqldb_directory = str(here(app_config["directories"]["sqldb_directory"]))
        self.uploaded_files_sqldb_directory = str(here(app_config["directories"]["uploaded_files_sqldb_directory"]))
        self.stored_csv_xlsx_sqldb_directory = str(here(app_config["directories"]["stored_csv_xlsx_sqldb_directory"]))
        self.persist_directory = str(here(app_config["directories"]["persist_directory"]))

    def load_llm_configs(self, app_config: dict):
        self.agent_llm_system_role = app_config["llm_config"].get("agent_llm_system_role", "")
        self.rag_llm_system_role = app_config["llm_config"].get("rag_llm_system_role", "")
        self.temperature = app_config["llm_config"].get("temperature", 0.1)

    def load_models(self):
        groq_token = os.getenv("GROQ_API_KEY", "")
        
        # We use openai/gpt-oss-20b which is available and tested on this Groq account
        self.groq_llm = ChatGroq(
            model="openai/gpt-oss-20b",
            groq_api_key=groq_token,
            temperature=self.temperature
        )
        # Point langchain_llm to groq_llm for uniform high-performance query generation
        self.langchain_llm = self.groq_llm

    def load_chroma_client(self):
        os.makedirs(self.persist_directory, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=self.persist_directory
        )

    def load_rag_config(self, app_config: dict):
        self.collection_name = app_config["rag_config"].get("collection_name", "default_collection")
        self.top_k = app_config["rag_config"].get("top_k", 1)

    def remove_directory(self, directory_path: str):
        if os.path.exists(directory_path):
            try:
                shutil.rmtree(directory_path)
                print(f"The directory '{directory_path}' has been successfully removed.")
            except OSError as e:
                print(f"Error: {e}")
        else:
            print(f"The directory '{directory_path}' does not exist.")
