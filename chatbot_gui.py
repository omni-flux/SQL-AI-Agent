import gradio as gr
import requests
import json

# --- Configuration ---
FASTAPI_URL = "http://127.0.0.1:8000"
CHAT_ENDPOINT = f"{FASTAPI_URL}/chat"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/"
BOT_TITLE = "SQL-AI Chatbot 🤖"

# --- Backend Interaction Logic ---
def call_chatbot_api(user_message: str):
    """Sends message to the FastAPI backend and returns the response parts."""
    payload = {"user_message": user_message}
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=120)
        # Handle API errors
        if response.status_code >= 400:
            error_detail = f"API Error {response.status_code}"
            try:
                error_detail += f": {response.json().get('detail', 'Unknown error')}"
            except json.JSONDecodeError:
                error_detail += f": {response.text[:100]}"
            return None, None, None, error_detail

        # Process successful response
        response_data = response.json()
        ai_msg = response_data.get("ai_message")
        exec_status = response_data.get("execution_status")
        executing_cmd = response_data.get("executing_command")

        return ai_msg, exec_status, executing_cmd, None # No error

    except requests.exceptions.Timeout:
        return None, None, None, "Error: The request to the backend timed out."
    except requests.exceptions.ConnectionError:
        return None, None, None, f"Error: Could not connect to the backend API at {FASTAPI_URL}. Is it running?"
    except requests.exceptions.RequestException as e:
        return None, None, None, f"Error: An unexpected request error occurred: {e}"
    except Exception as e:
        return None, None, None, f"Error: A local error occurred: {str(e)}"

def respond(message, chat_history):
    """
    Called when the user submits a message.
    Appends user message, shows thinking indicator, calls API, updates indicator with response.
    """
    chat_history.append({"role": "user", "content": message})

    thinking_indicator_html = "<span class='thinking-dot'></span>"
    chat_history.append({"role": "assistant", "content": thinking_indicator_html})

    yield chat_history, "", ""

    # Call the backend API (this takes time)
    ai_msg, exec_status, executing_cmd, error_msg = call_chatbot_api(message)

    # Prepare strings for display (even if None)
    status_display = f"*{exec_status}*" if exec_status else ""
    executing_display = f"{executing_cmd}" if executing_cmd else ""

    response_text = ""
    if error_msg:
        response_text = error_msg
        status_display = ""
        executing_display = ""
    elif ai_msg:
        response_text = ai_msg
    else:
        response_text = "Received no response content from the backend."
        status_display = ""
        executing_display = ""

    if chat_history and chat_history[-1]["role"] == "assistant":
        chat_history[-1]["content"] = response_text
    else:
        # Fallback if something went wrong (shouldn't normally happen)
        chat_history.append({"role": "assistant", "content": response_text})

    yield chat_history, status_display, executing_display

# --- Gradio UI Definition ---
custom_css = """
.gradio-container, .gradio-container *, .gradio-container p, .gradio-container input, .gradio-container button, .gradio-container label, .gradio-container textarea {
    font-size: 22px !important;
}
.gradio-container h1 {
    font-size: 46px !important;
}
.gradio-container h2 {
    font-size: 11px !important;
}
.gradio-container h3 {
    font-size: 18px !important;
}
#chatbot .message {
    font-size: 20px !important;
}
#chatbot .message.user {
    align-self: flex-end !important;
    margin-left: auto;
    margin-right: 10px; /* Optional: small gap from edge */
}
#chatbot .message.bot {
    background: none !important;   
    border: none !important;       
    box-shadow: none !important;    
    padding: 5px 10px !important;   
    align-self: flex-start !important;
    margin-right: auto;
    margin-left: 10px; 
    /* color: #333 !important; */
}
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.2; }
}

/* Style the thinking dot itself */
.thinking-dot {
    display: inline-block; /* Allow sizing */
    /* --- CHANGE THESE VALUES --- */
    width: 12px;          /* Increased dot size */
    height: 12px;         /* Increased dot size */
    /* --- END OF CHANGES --- */
    background-color: white; /* Dot color */
    border-radius: 50%;   /* Make it round */
    margin: 5px 0;        /* Adjust margin if needed for new size */
    animation: blink 1.2s infinite ease-in-out; 
}
/* Ensure the bot message container aligns the dot correctly */
#chatbot .message.bot {
    /* Keep existing styles: background: none, align-self: flex-start, etc. */
    /* Add display flex to help align the dot if needed, though inline-block often works */
    display: flex;
    align-items: center; 
    min-height: 28px; 
}
"""

with gr.Blocks(theme=gr.themes.Base(), css=custom_css, title=BOT_TITLE) as demo:
    gr.Markdown(f"# {BOT_TITLE}")
    gr.Markdown("Ask questions or give commands related to your database.")

    try:
        health_resp = requests.get(HEALTH_ENDPOINT, timeout=5)
        health_data = health_resp.json()
        if health_resp.status_code == 200 and health_data.get("code") == 200:
             gr.Markdown("✅ Backend API Status: Connected", elem_id="api_status_ok")
        else:
             status_detail = health_data.get('status', 'Unknown status')
             gr.Markdown(f"⚠️ Backend API Status: {status_detail}", elem_id="api_status_warn")
    except Exception:
        gr.Markdown(f"❌ Backend API Status: Connection Failed at {HEALTH_ENDPOINT}", elem_id="api_status_err")

    chatbot = gr.Chatbot(
        [],
        elem_id="chatbot",
        show_label=False,
        type='messages',
        height=600,
    )

    with gr.Row():
         executing_output = gr.Markdown("", elem_id="executing-output")
         status_output = gr.Markdown("", elem_id="status-output")

    with gr.Row():
        txt = gr.Textbox(
            scale=4,
            show_label=False,
            placeholder="Enter your message (e.g., 'show me all products', 'what are the tables?')",
            container=False,
        )

    txt.submit(
        respond,
        [txt, chatbot],
        [chatbot, status_output, executing_output],
        queue=True
    ).then(
        lambda: gr.Textbox(value=""),
        [],
        [txt],
        api_name=False
    )

    gr.Examples(
        examples=[
            "what tables are in the database?",
            "show me the first 5 products",
            "add a product named 'Super Widget' category 'Gadgets' price 99.99",
            "😊 thank you for your help",
        ],
        inputs=txt,
        label="Example Prompts"
    )
if __name__ == "__main__":
    print("Launching Gradio Chat Interface...")
    print(f"Make sure the FastAPI backend is running at {FASTAPI_URL}")
    demo.launch(server_name="127.0.0.1")