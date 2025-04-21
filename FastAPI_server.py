import os
import logging
import traceback
from typing import Optional
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

from tools.sql_tool import get_schema_info
from gemini_sql_chatbot import (
    db_config,
    initialize_chat_session,
    process_interaction,
)

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

load_dotenv()

app_state = {"chat_session": None, "schema_info": None, "initialized": False, "initialization_error": None}

# --- Pydantic Models ---
class UserInput(BaseModel):
    user_message: str

class AIResponse(BaseModel):
    ai_message: str
    executing_command: Optional[str] = None
    execution_status: Optional[str] = None

# --- Lifespan ---
# Corrected: Parameter renamed to _app to avoid shadowing and indicate unused status
@asynccontextmanager
async def lifespan(_app: FastAPI): # Changed 'app' to '_app'
    # Startup
    log.warning("Initializing application...")
    print("--- Initializing SQL-AI ---")
    error_msg = None
    required_db_keys = ['host', 'user', 'password', 'database']
    missing_db = [k for k in required_db_keys if not db_config.get(k)]
    if missing_db: error_msg = f"DB config incomplete (Missing: {', '.join(missing_db)})"
    if not os.environ.get("GEMINI_API_KEY"): error_msg = "GEMINI_API_KEY not found."

    if error_msg:
        app_state["initialization_error"] = error_msg
        log.critical(f"Startup failed: {error_msg}")
        print(f"FATAL ERROR: {error_msg}")
        yield # Must yield control once
        log.warning("Application shutting down (startup failed).")
        # Removed explicit 'return' here, function ends naturally
        return # Removed explicit return None here

    # Proceed with initialization if no early errors
    try:
        print("   Loading schema...")
        schema = await get_schema_info(db_config)
        if schema.startswith("Schema Error:"): raise ConnectionError(schema)
        app_state["schema_info"] = schema
        print("   Schema OK.")

        print("   Initializing AI...")
        session = initialize_chat_session(schema, db_config.get('database', ''))
        if session is None: raise RuntimeError("AI chat session initialization failed.")
        app_state["chat_session"] = session
        print("   AI OK.")

        app_state["initialized"] = True
        app_state["initialization_error"] = None
        print("--- Initialization Complete ---")
        log.warning("Application startup successful.")

    except Exception as e:
        app_state["initialization_error"] = f"Startup error: {str(e)}"
        app_state["initialized"] = False
        log.critical(app_state["initialization_error"], exc_info=True)
        print(f"\nFATAL STARTUP ERROR: {app_state['initialization_error']}")
        traceback.print_exc()
        # Proceed to yield even if init fails, so server starts and reports error via health check

    # --- App runs here ---
    yield
    # --- Shutdown ---
    log.warning("Application shutting down.")
    print("\n--- Server Shutting Down ---")
    app_state["chat_session"] = None # Clear state on shutdown
    app_state["initialized"] = False
    # No explicit return needed here either, implicitly returns None

# --- FastAPI App ---
# Define the global 'app' instance *after* the lifespan function
app = FastAPI(
    title="SQL AI Assistant API",
    description="Gemini-powered SQL AI chatbot.",
    version="1.3.1",
    lifespan=lifespan # Pass the lifespan manager
)

# --- API Endpoints ---
@app.get("/", summary="Health Check", tags=["Status"])
async def read_root():
    if not app_state["initialized"]:
        # Return the status and code directly
        return {"status": f"Initialization failed: {app_state['initialization_error']}", "code": 503}
    else:
        # Return the status and code directly
        return {"status": "API Initialized and Running", "code": 200}


@app.post("/chat", response_model=AIResponse, summary="Process Message", tags=["Chat"])
async def chat_endpoint(user_input: UserInput):
    if not app_state["initialized"]:
        raise HTTPException(status_code=503, detail=f"Service Unavailable: {app_state['initialization_error']}")
    session = app_state.get("chat_session")
    if not session:
        log.error("Chat req when session invalid.")
        raise HTTPException(status_code=500, detail="Internal Server Error: Chat session missing.")
    msg = user_input.user_message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="User message cannot be empty.")

    log.info(f"Processing chat: '{msg[:50]}...'")
    try:
        final_response_msg, exec_status, executing_msg = await process_interaction(msg, db_config, session)

        log.info(f"Response: '{final_response_msg[:100]}...' | Status: {exec_status} | Executing: {executing_msg}")
        return AIResponse(
            ai_message=final_response_msg,
            execution_status=exec_status,
            executing_command=executing_msg
        )

    except HTTPException: raise
    except Exception as e:
        log.error(f"Error during chat processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error processing request.")

# --- Run Server ---
if __name__ == "__main__":
    print("Starting FastAPI server via uvicorn...")
    # Make sure to reference the global 'app' instance here
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)