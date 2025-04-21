import gradio as gr
import requests
import json

# --- Configuration ---
FASTAPI_URL = "http://127.0.0.1:8000"  # Your FastAPI backend URL
CHAT_ENDPOINT = f"{FASTAPI_URL}/chat"
HEALTH_ENDPOINT = f"{FASTAPI_URL}/"
BOT_TITLE = "SQL-AI Chatbot 🤖"

# --- Backend Interaction Logic ---
def call_chatbot_api(user_message: str):
    """Sends message to the FastAPI backend and returns the response parts."""
    payload = {"user_message": user_message}
    try:
        response = requests.post(CHAT_ENDPOINT, json=payload, timeout=120) # Increased timeout for potentially long queries

        # Handle API errors
        if response.status_code >= 400:
            error_detail = f"API Error {response.status_code}"
            try:
                error_detail += f": {response.json().get('detail', 'Unknown error')}"
            except json.JSONDecodeError:
                error_detail += f": {response.text[:100]}" # Show raw text if not JSON
            return None, None, None, error_detail # ai_msg, status, executing, error

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
    Appends user message, calls API, appends status/AI response.
    """
    chat_history.append([message, None])
    yield chat_history, "", ""

    # Call the backend API
    ai_msg, exec_status, executing_cmd, error_msg = call_chatbot_api(message)

    # Prepare strings for display (even if None)
    status_display = f"*{exec_status}*" if exec_status else ""
    executing_display = f"```{executing_cmd}```" if executing_cmd else "" # Use markdown code block

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

    chat_history[-1][1] = response_text

    yield chat_history, status_display, executing_display


# --- Gradio UI Definition ---
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue", secondary_hue="sky"), title=BOT_TITLE) as demo:
    gr.Markdown(f"# {BOT_TITLE}")
    gr.Markdown("Ask questions or give commands related to your database.")

    # Health check indicator (optional but nice)
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


    # Chat display
    chatbot = gr.Chatbot(
        [], # Start with empty history
        elem_id="chatbot",
        label="Conversation",
        bubble_full_width=False,
        height=600,
    )

    # Hidden fields to display status below the chat input
    with gr.Row():
         executing_output = gr.Markdown("", elem_id="executing-output") # Will show "Executing..."
         status_output = gr.Markdown("", elem_id="status-output") # Will show "Successful/Failed"

    # User input area
    with gr.Row():
        txt = gr.Textbox(
            scale=4, # Make textbox wider
            show_label=False,
            placeholder="Enter your message (e.g., 'show me all products', 'what are the tables?')",
            container=False,
        )



    txt.submit(
        respond,                    # Function to call
        [txt, chatbot],             # Inputs: Textbox content, current Chatbot state
        [chatbot, status_output, executing_output], # Outputs: Update Chatbot, Status Markdown, Executing Markdown
        queue=True                  # Allow multiple users/requests concurrently
    ).then(
        lambda: gr.Textbox(value=""), # Function to clear textbox
        [],                           # No inputs needed for clearing
        [txt],                        # Output: Target the textbox
        api_name=False # Don't expose this clearing function as an API endpoint
    )

    gr.Examples(
        examples=[
            "hello",
            "what tables are in the database?",
            "show me the first 5 products",
            "describe the anime table",
            "add a product named 'Super Widget' category 'Gadgets' price 99.99", # Example requires specific table
        ],
        inputs=txt,
        label="Example Prompts"
    )

# --- Launch the App ---
if __name__ == "__main__":
    print("Launching Gradio Chat Interface...")
    print(f"Make sure the FastAPI backend is running at {FASTAPI_URL}")
    demo.launch(server_name="127.0.0.1")