# Table Talk — AI-Powered SQL & Tabular Data Chatbot

An AI-powered chatbot that helps users interact with structured data using natural-language questions. Instead of writing SQL queries manually, users can ask questions about their data and receive answers through a conversational interface.

The application supports CSV and Excel (`.xlsx`) file uploads, SQL-based querying, and a retrieval-augmented generation (RAG) option.

## 📌 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [How It Works](#-how-it-works)
- [Project Structure](#-project-structure)
- [Application Screenshots](#-application-screenshots)
- [Installation and Setup](#-installation-and-setup)
- [How to Use](#-how-to-use)
- [Example Questions](#-example-questions)
- [Troubleshooting](#-troubleshooting)
- [Future Improvements](#-future-improvements)

## 🚀 Overview

Table Talk is a Python-based conversational application designed to make tabular data easier to explore.

Users can upload supported data files and ask questions in natural language. The application provides different modes for interacting with stored SQL databases, stored tabular data, uploaded CSV/XLSX files, and a ChromaDB-based RAG workflow.

The user interface is built with Gradio, while LangChain and a language model help support the question-answering workflow.

**Goal:** Make data exploration more accessible to users who may not know SQL.

## ✨ Features

- **Natural-language question answering:** Ask questions about structured data using everyday language.
- **CSV and Excel uploads:** Upload `.csv` and `.xlsx` files through the interface.
- **SQL database interaction:** Work with data stored in SQL databases.
- **Uploaded-file querying:** Ask questions about uploaded tabular files through the SQL database workflow.
- **Multiple chat modes:** Choose between stored SQL data, stored CSV/XLSX SQL data, uploaded CSV/XLSX SQL data, and the available ChromaDB RAG option.
- **Conversational interface:** Submit questions and view responses in a Gradio chat window.
- **Python-based processing:** Use Python libraries to process data and connect the application components.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Gradio | Web-based chat interface and file upload controls |
| LangChain | Language-model orchestration and SQL question-answering workflow |
| Groq integration | Connects the application to a supported language model |
| SQLAlchemy | SQL database integration |
| SQLite | Database option for tabular data |
| Pandas | Tabular data processing |
| ChromaDB | Vector database for the RAG workflow |
| LangGraph | Included dependency for graph-based application workflows |
| python-dotenv | Loading configuration from environment variables |
| PyYAML | Reading YAML configuration files |

## ⚙️ How It Works

The application follows a workflow that connects the user interface, data processing, and AI-assisted question answering.

1. **User input:** The user uploads a CSV/XLSX file or selects a supported stored-data mode.
2. **Data preparation:** The application processes the selected data source.
3. **Data access:** In the SQL workflow, the tabular data is made available through a SQL database.
4. **Question processing:** The user enters a question in natural language.
5. **Query generation:** The language-model workflow helps translate the question into a database query where applicable.
6. **Query execution:** The SQL workflow executes the generated query against the selected database.
7. **Answer display:** The application returns the result through the Gradio chat interface.

The RAG option uses a separate ChromaDB-based workflow. The exact processing steps depend on the selected mode and its configuration.

## 📂 Project Structure

```text
SQL-and-Tabular-Data-Chatbot/
│
├── app.py
├── requirements.txt
├── prepare_csv_xlsx_sqlitedb.py
├── prepare_csv_xlsx_vectordb.py
│
├── configs/
│   └── Application configuration files
│
├── data/
│   └── Stored data files
│
├── utils/
│   ├── chatbot.py
│   ├── upload_file.py
│   └── Other helper modules
│
├── .gitignore
└── README.md
```

*Note: The folder descriptions above are explanatory. Check the actual contents of `configs/`, `data/`, and `utils/` in the repository before documenting individual files.*

## 🖥️ Application Screenshots

Screenshots of the application will be added here to demonstrate the interface and main workflows.

### 1. Main Chat Interface

![Main Chat Interface](assets/screenshots/chatbot-home.png)

*The main interface for entering questions and viewing chatbot responses.*

### 2. Uploading a CSV or Excel File

![File Upload Interface](assets/screenshots/file-upload.png)

*The upload interface for supported CSV and XLSX files.*

### 3. Question and Answer Example

![Question Answer Example](assets/screenshots/question-answer.png)

*An example of asking a question about a dataset and viewing the response.*

### 4. SQL Querying Workflow

![SQL Query Workflow](assets/screenshots/sql-query.png)

*Add a screenshot showing a successful SQL-based question-answering interaction.*

> Replace these example image paths with your actual screenshot filenames. If you have not added screenshots yet, remove these image sections until the files are available.

## 💻 Installation and Setup

Follow these steps to run the project locally.

### Prerequisites

- Python installed on your computer
- Git
- A Groq API key if your selected model configuration requires one
- Visual Studio Code or another Python editor (optional)

### Step 1: Clone the repository

```bash
git clone https://github.com/shanmukpanchireddi/SQL-and-Tabular-Data-Chatbot..git
cd SQL-and-Tabular-Data-Chatbot.
```

### Step 2: Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the following command in that terminal session and try activating again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 4: Configure your API key

If the application uses a Groq API key, create a `.env` file in the project root and configure the variable name expected by the application.

For example, if the code reads `GROQ_API_KEY`:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

Replace the placeholder with your own key. Never commit the `.env` file or publish your API key.

### Step 5: Check the configuration

Review the files in `configs/` and confirm that any required model, data directory, or database settings point to valid locations on your computer.

### Step 6: Run the application

```bash
python app.py
```

Open the local URL printed in your terminal. The application typically runs at:

`http://127.0.0.1:7860`

The actual address may differ if the port is changed or unavailable.

## 📖 How to Use

1. Start the application using `python app.py`.
2. Open the local Gradio interface in your browser.
3. Choose the appropriate **App functionality** and **Chat type** options.
4. To query a file, click **Upload CSV or XLSX files** and select a supported file.
5. Wait for the upload and data preparation to complete.
6. Enter a question in the text box.
7. Click **Submit text** or press Enter.
8. Review the answer in the chat window.
9. Ask additional questions about the dataset as needed.

The available chat types include stored SQL database querying, stored CSV/XLSX SQL database querying, uploaded CSV/XLSX SQL database querying, and the ChromaDB RAG option.

## 💬 Example Questions

The questions below are examples of the kinds of queries you can try. The exact answer depends on the dataset you load.

- What is the total number of records?
- What is the average value of the selected numeric column?
- Which record has the highest value?
- Which record has the lowest value?
- How many records belong to each category?
- Show the records that match a particular condition.
- What is the total for a specified category?

For example, if your dataset contains house listings, you could ask:

- How many houses are in the dataset?
- Which house has the highest price?
- What is the average house price?
- How many houses are listed in Cambridge?

## 🧰 Troubleshooting

**1. Missing Python packages**

Install the dependencies again:

```bash
python -m pip install -r requirements.txt
```

**2. API key or authentication error**

Check that the API key is valid, the environment variable name matches the code, and the `.env` file is being loaded correctly.

**3. File upload or database error**

Verify that the uploaded file is a supported CSV or XLSX file and that the application has permission to access its working directories.

**4. Application does not open**

Check the terminal for error messages and open the exact local URL printed by Gradio.

**5. Chatbot returns an error instead of an answer**

Confirm that the correct chat type is selected, the database or file was processed successfully, and the configured language model is accessible.

## 🔮 Future Improvements

Potential enhancements include:

- Displaying generated SQL queries for greater transparency.
- Adding charts and visual summaries of query results.
- Improving error messages and query validation.
- Expanding support for additional data formats.
- Adding automated tests for file processing and SQL question answering.
- Deploying the application to a cloud hosting platform.

## 👨‍💻 Author

**Shanmukha Rao**

GitHub: [@shanmukpanchireddi](https://github.com/shanmukpanchireddi)

## 📄 License

No license has been specified in this repository yet. Add a license file if you intend to define permissions for others to use, modify, or distribute the project.
