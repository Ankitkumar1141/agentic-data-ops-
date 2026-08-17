import psycopg2


class DatabaseManager:
    """Manages PostgreSQL connections and dynamic schema introspection."""

    def __init__(self, db_config: dict):
        self.db_config = db_config
        try:
            self.connection = psycopg2.connect(**db_config)
        except Exception as e:
            print(f"Error connecting to database: {e}")
            self.connection = None

    def schema_details(self, schema_name: str = "public") -> str:
        """Introspects tables, columns, and sample records to provide LLM context."""
        if not self.connection:
            return "No active database connection."

        schema_context = f"Database Schema: {schema_name}\n"
        cursor = self.connection.cursor()

        try:
            # Query all table names in the target schema
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s;",
                (schema_name,)
            )
            tables = cursor.fetchall()

            for (table_name,) in tables:
                schema_context += f"\nTable: {table_name}\n"

                # Fetch column definitions
                cursor.execute(
                    "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;",
                    (table_name,)
                )
                for col_name, data_type in cursor.fetchall():
                    schema_context += f"  Column: {col_name}, Data Type: {data_type}\n"

                # Fetch up to 5 sample rows for few-shot data understanding
                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5;")
                schema_context += "  Sample Data:\n"
                for row in cursor.fetchall():
                    schema_context += f"    {row}\n"

        except Exception as e:
            schema_context = f"Error fetching schema details: {e}"
        finally:
            cursor.close()
            self.connection.close()

        return schema_context

    def execute_sql(self, query: str) -> str:
        """Executes a SQL query and returns fetched results."""
        if not self.connection:
            return "No active database connection."

        cursor = self.connection.cursor()
        try:
            cursor.execute(query)
            result = cursor.fetchall()
            self.connection.commit()
            return str(result)
        except Exception as e:
            return f"Error executing query: {e}"
        finally:
            cursor.close()
            self.connection.close()


DatabaseUtil = DatabaseManager


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    db_config = {
        "host": os.environ.get("host", "localhost"),
        "port": int(os.environ.get("port", 5432)),
        "user": os.environ.get("user", "postgres"),
        "password": os.environ.get("password", "postgres"),
        "dbname": os.environ.get("database", "postgres"),
    }

    manager = DatabaseManager(db_config)
    if manager.connection:
        schema = manager.schema_details("public")
        with open("sample_schema.txt", "w", encoding="utf-8") as f:
            f.write(schema)
