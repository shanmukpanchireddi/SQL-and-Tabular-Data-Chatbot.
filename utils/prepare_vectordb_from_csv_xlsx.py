import os
import pandas as pd
from utils.load_config import LoadConfig

class PrepareVectorDBFromTabularData:
    def __init__(self, file_directory: str) -> None:
        self.APPCFG = LoadConfig()
        self.file_directory = file_directory

    def run_pipeline(self):
        self.df, self.file_name = self._load_dataframe(file_directory=self.file_directory)
        self.docs, self.metadatas, self.ids = self._prepare_data_for_injection(df=self.df, file_name=self.file_name)
        self._inject_data_into_chromadb()
        self._validate_db()

    def _inject_data_into_chromadb(self):
        # Reset or get existing collection cleanly
        try:
            self.APPCFG.chroma_client.delete_collection(name=self.APPCFG.collection_name)
        except Exception:
            pass

        collection = self.APPCFG.chroma_client.create_collection(name=self.APPCFG.collection_name)
        
        # ChromaDB automatically generates embeddings for documents if embeddings parameter is not provided
        collection.add(
            documents=self.docs,
            metadatas=self.metadatas,
            ids=self.ids
        )
        print("==============================")
        print("Data is stored in ChromaDB successfully.")

    def _load_dataframe(self, file_directory: str):
        file_names_with_extensions = os.path.basename(file_directory)
        file_name, file_extension = os.path.splitext(file_names_with_extensions)
        if file_extension.lower() == ".csv":
            df = pd.read_csv(file_directory)
            return df, file_name
        elif file_extension.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(file_directory)
            return df, file_name
        else:
            raise ValueError("The selected file type is not supported")

    def _prepare_data_for_injection(self, df: pd.DataFrame, file_name: str):
        docs = []
        metadatas = []
        ids = []
        for index, row in df.iterrows():
            output_str = ""
            for col in df.columns:
                output_str += f"{col}: {row[col]}, "
            docs.append(output_str)
            metadatas.append({"source": file_name})
            ids.append(f"id_{index}")
        return docs, metadatas, ids

    def _validate_db(self):
        vectordb = self.APPCFG.chroma_client.get_collection(name=self.APPCFG.collection_name)
        print("==============================")
        print("Number of vectors in vectordb:", vectordb.count())
        print("==============================")