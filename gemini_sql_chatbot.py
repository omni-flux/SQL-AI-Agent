import os
import re
import google.generativeai as genai
from dotenv import load_dotenv
from tools.sql_tool import execute_sql
import logging
from typing import Tuple, Optional
from prompts import BASE_SYSTEM_PROMPT

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

load_dotenv()

# --- Config (No changes) ---
DB_HOST = os.environ.get("DB_HOST", "localhost"); DB_USER = os.environ.get("DB_USER"); DB_PASSWORD = os.environ.get("DB_PASSWORD"); DB_NAME = os.environ.get("DB_NAME")
db_config = {"host": DB_HOST, "user": DB_USER, "password": DB_PASSWORD, "database": DB_NAME}
try:
    gemini_api_key = os.environ.get("GEMINI_API_KEY"); assert gemini_api_key, "GEMINI_API_KEY not found."
    genai.configure(api_key=gemini_api_key)
except Exception as config_err: log.critical(f"Config Error: {config_err}", exc_info=True); print(f"FATAL: {config_err}"); exit(1)
MODEL_NAME = "gemini-1.5-flash"
generation_config = {"temperature": 0.4, "top_p": 0.95, "top_k": 64, "max_output_tokens": 8192, "response_mime_type": "text/plain"}
SAFETY_SETTINGS = [ {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
BASE_SYSTEM_PROMPT = BASE_SYSTEM_PROMPT

# --- Core Functions ---
def initialize_chat_session(schema_info: str, db_name: str):
    try:
        system_prompt = BASE_SYSTEM_PROMPT.format(schema_placeholder=schema_info, db_name=db_name)
        model = genai.GenerativeModel(MODEL_NAME, generation_config=generation_config, safety_settings=SAFETY_SETTINGS, system_instruction=system_prompt)
        return model.start_chat(history=[])
    except Exception as init_err: log.critical(f"Init Error: {init_err}", exc_info=True); print(f"FATAL INIT: {init_err}"); return None

def send_to_gemini(current_turn_content: str, session):
    if not session: return "Error: Chat session invalid."
    try:
        response = session.send_message(current_turn_content)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            return f"My response was blocked (Reason: {response.prompt_feedback.block_reason}). Rephrase."
        try:
            response_text = response.text
            if not response_text.strip(): return "AI returned empty response. Rephrase?"
            return response_text
        except (ValueError, AttributeError):
             rating_info = ""
             if not response.candidates: return "AI response unprocessable (no candidates)."
             return f"AI response unprocessable (filtered?).{rating_info} Rephrase."
    except Exception as send_err: log.error(f"Gemini API Error: {send_err}", exc_info=True); return f"AI comm error: {send_err}"

# Updated: Return type hint includes third element for executing message
async def find_and_execute_sql(text: str, current_db_config: dict) -> Optional[Tuple[str, str, str]]:
    """
    Finds `[SQL: ... ]`, executes it.
    Returns tuple: (tool_result_for_ai, status_msg_client, executing_msg_client) or None.
    """
    match = re.search(r'\[SQL:\s*(.*?)\s*]', text, re.DOTALL | re.IGNORECASE)
    if match:
        sql_command = match.group(1).strip('; \t\n\r ')
        status_message: Optional[str] = None
        executing_message: Optional[str] = None
        tool_result_for_ai = ""

        if sql_command:
            # --- Create executing message ---
            executing_message = f"[Executing SQL: {sql_command[:70]}{'...' if len(sql_command)>70 else ''}]"
            print(f"   {executing_message}") # Print to server console

            result = await execute_sql(sql_command, current_db_config)
            tool_result_for_ai = f"Tool execution result for '[SQL: {sql_command}]':\n{result}"

            if result.startswith(("Error:", "Failed", "SQL")):
                status_message = f"[SQL Execution Failed: {result.splitlines()[0]}]"
                log.warning(f"SQL exec failed: {result}")
            else:
                status_message = "[SQL Execution Successful]"
            print(f"   {status_message}") # Server console status print
            # --- Return all three parts ---
            return tool_result_for_ai, status_message, executing_message
        else:
            executing_message = "[Notice: Found empty SQL marker]" # Provide context
            status_message = "[No action taken]"
            tool_result_for_ai = f"Tool execution notice: Found empty SQL marker '[SQL: ]'."
            print(f"   {executing_message} {status_message}")
            log.warning(f"Found empty SQL marker: {match.group(0)}")
            return tool_result_for_ai, status_message, executing_message
    return None # No SQL found

# Updated: Return type hint and logic for the new tuple structure
async def process_interaction(user_input: str, current_db_config: dict, current_chat_session) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Handles one interaction turn.
    Returns tuple: (ai_message_user, exec_status_client, executing_msg_client)
    """
    if not current_chat_session:
         log.error("process_interaction with invalid session.")
         return "Error: Chat session invalid.", "[Internal Error]", None

    exec_status_client: Optional[str] = None
    executing_msg_client: Optional[str] = None

    # 1. User -> AI
    ai_response_text = send_to_gemini(user_input, current_chat_session)

    if ai_response_text.startswith(("Error:", "My response", "I received", "The AI response")):
        log.error(f"Initial AI error/block: {ai_response_text}")
        return ai_response_text, "[AI Error]", None # Return None for executing message

    # 2. Check for SQL -> Execute -> Get Result, Status, ExecutingMsg
    # Returns Optional[Tuple[str, str, str]]
    tool_outcome = await find_and_execute_sql(ai_response_text, current_db_config)

    final_response_to_show = ai_response_text

    if tool_outcome:
        # --- Unpack all three ---
        tool_result_content, exec_status_client, executing_msg_client = tool_outcome

        # 3. Tool Result -> AI for Synthesis
        log.debug("Sending tool result to AI for synthesis.")
        final_response_to_show = send_to_gemini(tool_result_content, current_chat_session)

        if final_response_to_show.startswith(("Error:", "My response", "I received", "The AI response")):
            log.error(f"Synthesis AI error/block: {final_response_to_show}")
            # Return AI error, but keep original status and executing message
            return f"Executed ({executing_msg_client} -> {exec_status_client}), but AI failed processing result: {final_response_to_show}", exec_status_client, executing_msg_client

    # 4. Clean and Finalize Response
    cleaned_response = re.sub(r'\[SQL:\s*.*?\s*]', '', final_response_to_show, flags=re.DOTALL | re.IGNORECASE).strip()

    if not cleaned_response:
        # Use status/executing messages for fallback context if available
        if exec_status_client and "Successful" in exec_status_client: cleaned_response = "OK. Action completed."
        elif exec_status_client and "Notice" in exec_status_client: cleaned_response = f"OK. Noticed an issue ({executing_msg_client}), no action taken."
        elif exec_status_client and "Failed" in exec_status_client: cleaned_response = f"Issue executing command ({executing_msg_client}). Check details."
        else: cleaned_response = "Lost my train of thought. Repeat request?"

    # Return final message, status, and executing message
    return cleaned_response, exec_status_client, executing_msg_client