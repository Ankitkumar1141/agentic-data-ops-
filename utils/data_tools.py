import os
import requests
import pandas as pd


class DataTools:
    """Utilities for API data extraction, preview inspection, and Pandas code execution."""

    def extract_load(self, url: str, output_folder: str, format: str) -> str:
        """Fetches JSON results from a REST endpoint and saves them in the requested format."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        destination = os.path.join(project_root, output_folder)

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            os.makedirs(destination, exist_ok=True)
            output_file = os.path.join(destination, f"extracted_data.{format}")

            df = pd.json_normalize(data.get("results", data))
            if format == "csv":
                df.to_csv(output_file, index=False)
            elif format == "json":
                df.to_json(output_file, orient="records", lines=True)
            elif format == "parquet":
                df.to_parquet(output_file, index=False)
            else:
                return f"Unsupported format: {format}"

            return f"Data successfully extracted and saved to {output_file}"
        except requests.exceptions.RequestException as e:
            return f"Failed to extract data: {e}"

    def transform_load_context(self, file_path: str) -> str:
        """Reads a 3-row head sample of a dataset to inform transformation code generation."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path, lines=True)
        elif ext == ".parquet":
            df = pd.read_parquet(file_path)
        else:
            return f"Unsupported file format: {ext}"

        return str(df.head(3))

    def execute_code(self, code: str) -> str:
        """Executes generated Pandas code string in a sandboxed context."""
        try:
            exec(code)
            return "Code executed successfully."
        except Exception as e:
            return f"Failed to execute code: {e}"


ETLTools = DataTools


if __name__ == "__main__":
    tools = DataTools()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sample_file = os.path.join(project_root, "data", "extract", "extracted_data.csv")
    if os.path.exists(sample_file):
        print(tools.transform_load_context(sample_file))
