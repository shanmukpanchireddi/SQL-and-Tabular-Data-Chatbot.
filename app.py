import gradio as gr
from utils.ui_settings import UISettings
from utils.upload_file import UploadFile
from utils.chatbot import ChatBot

with gr.Blocks(title="Table Talk - AI-Powered SQL Chatbot") as demo:
    gr.Markdown("# Table Talk 💬📊")
    gr.Markdown("### AI-Powered Chatbot for SQL Database & Tabular Data Interaction")

    with gr.Tabs():
        with gr.TabItem("Q&A-and-RAG-with-SQL-and-TabularData"):
            with gr.Row() as row_one:
                chatbot = gr.Chatbot(
                    [],
                    elem_id="chatbot",
                    bubble_full_width=False,
                    height=500
                )
                chatbot.like(UISettings.feedback, None, None)

            with gr.Row():
                input_txt = gr.Textbox(
                    lines=3,
                    scale=8,
                    placeholder="Enter your question here (e.g., 'Show total sales', 'What is the average age?') and press Enter or click Submit text",
                    container=False,
                )

            with gr.Row() as row_two:
                text_submit_btn = gr.Button(value="Submit text", variant="primary")
                upload_btn = gr.UploadButton(
                    "📁 Upload CSV or XLSX files", file_types=['.csv', '.xlsx'], file_count="multiple")
                app_functionality = gr.Dropdown(
                    label="App functionality", choices=["Chat", "Process files"], value="Chat")
                chat_type = gr.Dropdown(
                    label="Chat type", choices=[
                        "Q&A with stored SQL-DB",
                        "Q&A with stored CSV/XLSX SQL-DB",
                        "RAG with stored CSV/XLSX ChromaDB",
                        "Q&A with Uploaded CSV/XLSX SQL-DB"
                    ], value="Q&A with stored SQL-DB")
                clear_button = gr.ClearButton([input_txt, chatbot])
            
            def handle_upload(files, chatbot_hist, app_func):
                txt, updated_hist = UploadFile.run_pipeline(files, chatbot_hist, app_func)
                # Automatically update chat_type dropdown to 'Q&A with Uploaded CSV/XLSX SQL-DB' upon uploading
                return txt, updated_hist, gr.update(value="Q&A with Uploaded CSV/XLSX SQL-DB")

            upload_btn.upload(
                fn=handle_upload,
                inputs=[upload_btn, chatbot, app_functionality],
                outputs=[input_txt, chatbot, chat_type],
                queue=False
            )
            
            input_txt.submit(
                fn=ChatBot.respond,
                inputs=[chatbot, input_txt, chat_type, app_functionality],
                outputs=[input_txt, chatbot],
                queue=False
            )

            text_submit_btn.click(
                fn=ChatBot.respond,
                inputs=[chatbot, input_txt, chat_type, app_functionality],
                outputs=[input_txt, chatbot],
                queue=False
            )

if __name__ == "__main__":
    demo.launch()