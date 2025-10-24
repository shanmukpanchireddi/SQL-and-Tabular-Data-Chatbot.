import os
from typing import List, Tuple
from utils.load_config import LoadConfig
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter
from sqlalchemy import create_engine
from langchain_community.agent_toolkits import create_sql_agent
import langchain
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
langchain.debug = True

os.environ["GROQ_API_KEY"]= ""

APPCFG = LoadConfig()

class ChatBot:
    @staticmethod
    def respond(chatbot: List, message: str, chat_type: str, app_functionality: str) -> Tuple:
        if app_functionality == "Chat":
            if chat_type == "Q&A with stored SQL-DB":
                if os.path.exists(APPCFG.sqldb_directory):
                    db = SQLDatabase.from_uri(
                        f"sqlite:///{APPCFG.sqldb_directory}")
                    execute_query = QuerySQLDataBaseTool(db=db)
                    write_query = create_sql_query_chain(
                        APPCFG.langchain_llm, db)
                    answer_prompt = PromptTemplate.from_template(
                        APPCFG.agent_llm_system_role)
                    answer = answer_prompt | APPCFG.langchain_llm | StrOutputParser()
                    chain = (
                        RunnablePassthrough.assign(query=write_query).assign(
                            result=itemgetter("query") | execute_query
                        )
                        | answer
                    )
                    response = chain.invoke({"question": message})
                else:
                    chatbot.append(
                        (message, f"SQL DB does not exist. Please first create the 'sqldb.db'."))
                    return "", chatbot, None
            elif chat_type == "Q&A with Uploaded CSV/XLSX SQL-DB" or chat_type == "Q&A with stored CSV/XLSX SQL-DB":
                if chat_type == "Q&A with Uploaded CSV/XLSX SQL-DB":
                    if os.path.exists(APPCFG.uploaded_files_sqldb_directory):
                        engine = create_engine(
                            f"sqlite:///{APPCFG.uploaded_files_sqldb_directory}")
                        db = SQLDatabase(engine=engine)
                        print(db.dialect)
                    else:
                        chatbot.append(
                            (message, f"SQL DB from the uploaded csv/xlsx files does not exist. Please first upload the csv files from the chatbot."))
                        return "", chatbot, None
                elif chat_type == "Q&A with stored CSV/XLSX SQL-DB":
                    if os.path.exists(APPCFG.stored_csv_xlsx_sqldb_directory):
                        engine = create_engine(
                            f"sqlite:///{APPCFG.stored_csv_xlsx_sqldb_directory}")
                        db = SQLDatabase(engine=engine)
                    else:
                        chatbot.append(
                            (message, f"SQL DB from the stored csv/xlsx files does not exist. Please first execute `src/prepare_csv_xlsx_sqlitedb.py` module."))
                        return "", chatbot, None
                print(db.dialect)
                print(db.get_usable_table_names())
                toolkit = SQLDatabaseToolkit(db=db, llm=APPCFG.langchain_llm)

                tools = toolkit.get_tools()
                SQL_PREFIX = """You are an agent designed to interact with a SQL database.
                Given an input question, create a syntactically correct SQLite query to run, then look at the results of the query and return the answer.
                Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
                You can order the results by a relevant column to return the most interesting examples in the database.
                Never query for all the columns from a specific table, only ask for the relevant columns given the question.
                You have access to tools for interacting with the database.
                Only use the below tools. Only use the information returned by the below tools to construct your final answer.
                You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

                DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

                To start you should ALWAYS look at the tables in the database to see what you can query.
                Do NOT skip this step.
                Then you should query the schema of the most relevant tables."""

                llm = ChatGroq(model="llama3-8b-8192")
                system_message = SystemMessage(content=SQL_PREFIX)
                agent_executor = create_react_agent(llm, tools)

                
                for s in agent_executor.stream({"messages": [system_message, HumanMessage(content=message)]}):
                    response = s

                response = response["agent"]["messages"][0].content


            elif chat_type == "RAG with stored CSV/XLSX ChromaDB":
                pass
            chatbot.append(
                (message, response))
            return "", chatbot
        else:
            pass
                
