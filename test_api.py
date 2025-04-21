import requests
import json
import sys

API_BASE_URL = "http://127.0.0.1:8000"
CHAT_URL = f"{API_BASE_URL}/chat"

print("Simple API Chat Client (Type 'exit' to quit)")
print("-" * 30)

# Initial Health Check (No changes)
try:
    health_response = requests.get(API_BASE_URL + "/"); health_data = health_response.json()
    if health_response.status_code != 200 or health_data.get("code") != 200:
        print(f"[Error] Server health check ({health_data.get('code', health_response.status_code)}): {health_data.get('status', 'Unknown')}")
        sys.exit("Exiting client.")
    print("[Server Status: OK]")
except requests.exceptions.ConnectionError: print(f"[Fatal] Cannot connect to {API_BASE_URL}"); sys.exit("Exiting.")
except Exception as e: print(f"[Fatal] Health check error: {e}"); sys.exit("Exiting.")

# Main chat loop
while True:
    try:
        user_msg = input("You: ").strip()
        if user_msg.lower() == 'exit': break
        if not user_msg: continue

        payload = {"user_message": user_msg}
        response = requests.post(CHAT_URL, json=payload)

        if response.status_code >= 400:
            error_detail = "Unknown error"
            try: error_detail = response.json().get('detail', error_detail)
            except json.JSONDecodeError: pass
            print(f"AI [Error {response.status_code}]: {error_detail}")
            continue

        # Process successful response
        response_data = response.json()

        # --- Updated: Check for and print *both* status messages ---
        executing_cmd = response_data.get("executing_command")
        exec_status = response_data.get("execution_status")

        if executing_cmd:
            print(f"   {executing_cmd}") # Print executing message first
        if exec_status:
            print(f"   {exec_status}") # Then print success/failure status
        # --- End of Update ---

        ai_msg = response_data.get("ai_message", "Error: No message in response")
        print(f"AI: {ai_msg}")


    except requests.exceptions.ConnectionError: print("\n[Connection Error] Lost server connection."); break
    except requests.exceptions.RequestException as e: print(f"\n[Request Error]: {e}")
    except Exception as e: print(f"\n[Client error]: {e}")

print("-" * 30)
print("Exiting chat client.")