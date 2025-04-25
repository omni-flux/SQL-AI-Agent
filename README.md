# SQL-AI-Agent

SQL-AI-Agent is an intelligent assistant that enables natural language interaction with a MySQL database. Leveraging a Large Language Model (LLM), it translates user queries into SQL commands, executes them, and returns the results seamlessly. This tool simplifies database querying, making it accessible even to those without SQL expertise.

<img src="https://github.com/user-attachments/assets/951ef8c2-ad50-4b37-a09d-b9be2cc6f91f" width="700"/>

## 🚀 Features

*   **Natural Language to SQL:** Converts plain English queries into SQL statements.
*   **Real-time Execution:** Runs SQL queries against a connected MySQL database.
*   **Interactive Interface:** Offers both GUI and API endpoints for user interaction.
*   **Configurable Environment:** Easily set up with customizable environment variables.

## 🛠️ Installation

### Prerequisites

*   Python 3.8 or higher
*   MySQL Server
*   A valid Gemini API key

### Steps

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/omni-flux/SQL-AI-Agent.git
    cd SQL-AI-Agent
    ```

2.  **Set Up Environment Variables**
    Duplicate the `.env example` file and rename it to `.env`.
    Populate the `.env` file with your credentials:
    ```ini
    GEMINI_API_KEY=your_gemini_api_key
    DB_HOST=localhost
    DB_USER=your_db_username
    DB_PASSWORD=your_db_password
    DB_NAME=your_database_name
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the Application**
    *   For the FastAPI server:
        ```bash
        python main.py
        ```
    *   For the GUI:
        ```bash
        python chatbot_gui.py
        ```

## 📁 Project Structure
*   `chatbot_gui.py`: Launches the graphical user interface.
*   `main.py`: Starts the FastAPI server for API interactions.
*   `gemini_sql_chatbot.py`: Core logic for processing and executing queries.
*   `prompts.py`: Contains prompt templates for the LLM.
*   `tools/sql_tool.py`: The mysql code execution tool
*   `.env example`: Sample environment configuration file.

## 📄 License
This project is licensed under the MIT License.
