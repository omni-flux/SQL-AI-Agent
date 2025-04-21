# tools/sql_tool.py
import mysql.connector
from mysql.connector import Error
import pandas as pd
import logging

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

MAX_ROWS_DISPLAY = 50
MAX_COLS_DISPLAY = 20
DISPLAY_WIDTH = 1000
pd.set_option('display.max_rows', MAX_ROWS_DISPLAY)
pd.set_option('display.max_columns', MAX_COLS_DISPLAY)
pd.set_option('display.width', DISPLAY_WIDTH)

async def get_schema_info(db_config: dict) -> str:
    """Connects to MySQL and retrieves schema information."""
    schema_info = "Database Schema:\n"
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config, connect_timeout=5)
        if not connection.is_connected():
            log.error("Schema Error: Could not connect to the database.")
            return "Schema Error: Could not connect to the database."

        cursor = connection.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        if not tables:
            log.warning(f"Schema Info: No tables found in database '{db_config.get('database')}'.")
            return "Schema Info: No tables found in the database."

        table_names = [table[0] for table in tables]
        schema_info += f"Tables: {', '.join(table_names)}\n\n"

        for table_name in table_names:
            try:
                cursor.execute(f"DESCRIBE `{table_name}`;")
                columns = cursor.fetchall()
                schema_info += f"Table `{table_name}` columns:\n"
                col_descriptions = []
                for col in columns: # (Field, Type, Null, Key, Default, Extra)
                    col_desc = f"  - `{col[0]}` ({col[1]})" # Name (Type)
                    if col[3]: col_desc += f" [{col[3]}]"      # Key
                    if col[5]: col_desc += f" [{col[5]}]"      # Extra
                    if col[2] == "NO": col_desc += " [NOT NULL]"
                    if col[4] is not None: col_desc += f" [Default: {col[4]}]"
                    col_descriptions.append(col_desc)
                schema_info += "\n".join(col_descriptions) + "\n\n"
            except Error as desc_err:
                schema_info += f"  Error describing table `{table_name}`: {desc_err.msg}\n\n"
                log.warning(f"Could not describe table `{table_name}`: {desc_err.msg}")

        return schema_info.strip()

    except Error as err:
        log.error(f"MySQL Error fetching schema: {err.errno}, {err.msg}", exc_info=True)
        return f"Schema Error: Failed to retrieve schema. {err.msg}"
    except Exception as e:
        log.error(f"General Error fetching schema: {str(e)}", exc_info=True)
        return f"Schema Error: An unexpected error occurred: {str(e)}"
    finally:
        if cursor: cursor.close()
        if connection and connection.is_connected(): connection.close()

async def execute_sql(sql_command: str, db_config: dict) -> str:
    """Connects to MySQL, executes SQL, returns results/status string."""
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(**db_config, connect_timeout=15)
        if not connection.is_connected():
            log.error("SQL Execution Error: Could not connect to the database.")
            return "Error: Could not connect to the database."

        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql_command)

        command_type = sql_command.strip().upper().split(maxsplit=1)[0] if sql_command.strip() else ""

        if command_type in ("SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN"):
            results = cursor.fetchall()
            if not results:
                return "Query executed successfully, no results returned."
            else:
                try:
                    df = pd.DataFrame(results)
                    num_rows = len(df)
                    if num_rows > MAX_ROWS_DISPLAY:
                         output = f"Query Results (showing first {MAX_ROWS_DISPLAY} of {num_rows} rows):\n{df.head(MAX_ROWS_DISPLAY).to_string(index=False)}"
                    else:
                         output = f"Query Results:\n{df.to_string(index=False)}"
                    return output
                except Exception as format_err:
                     log.error(f"Error formatting results with Pandas: {format_err}", exc_info=True)
                     preview = str(results[:5]) + ('...' if len(results) > 5 else '') # Shorter preview
                     return f"Query successful ({len(results)} rows), error formatting: {format_err}\nRaw preview: {preview}"
        else: # DML/DDL
            try:
                connection.commit()
                row_count = cursor.rowcount
                if row_count == -1:
                    return f"Command '{command_type}' executed successfully."
                else:
                    return f"Command executed successfully. {row_count} row(s) affected."
            except Error as commit_err:
                 log.error(f"Commit Error for '{sql_command[:100]}...': {commit_err.msg}", exc_info=True)
                 try: connection.rollback()
                 except Exception: pass
                 return f"Commit failed for '{command_type}' command: {commit_err.msg}. Rollback attempted."

    except mysql.connector.ProgrammingError as prog_err:
        log.warning(f"SQL Programming Error: {prog_err.msg} (Code: {prog_err.errno}) | Query: '{sql_command[:100]}...'")
        return f"SQL Programming Error: {prog_err.msg} (Code: {prog_err.errno})"
    except mysql.connector.IntegrityError as int_err:
        log.warning(f"SQL Integrity Error: {int_err.msg} (Code: {int_err.errno}) | Query: '{sql_command[:100]}...'")
        return f"SQL Integrity Error: {int_err.msg} (Code: {int_err.errno})"
    except mysql.connector.Error as err:
        log.error(f"MySQL Error executing SQL: {err.msg} (Code: {err.errno})", exc_info=True)
        return f"Database Error: {err.msg} (Code: {err.errno})"
    except Exception as e:
        log.error(f"General Error executing SQL: {str(e)}", exc_info=True)
        return f"Unexpected error during SQL execution: {str(e)}"
    finally:
        if cursor: cursor.close()
        if connection and connection.is_connected(): connection.close()