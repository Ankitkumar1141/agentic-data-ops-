import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.model_provider import get_llm, pick_llm
from utils.data_tools import DataTools, ETLTools
from models.schemas import ETLAgentSchema
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langchain.tools import tool


@tool
def extract_load_tool(url: str, output_folder: str, format: str) -> str:
    """
    Extracts data from a REST API endpoint and saves it locally.

    Args:
        url: The API endpoint URL to extract data from.
        output_folder: Destination directory for the extracted file.
        format: File format ('csv', 'json', 'parquet').
    """
    tools = DataTools()
    return tools.extract_load(url, output_folder, format)


@tool
def transform_load_tool(input_file_path: str, output_folder: str, output_format: str, user_question: str) -> str:
    """
    Inspects data preview, generates required Pandas transformation code, and executes it.

    Args:
        input_file_path: Path to the raw source data file.
        output_folder: Destination directory for the transformed file.
        output_format: Output format ('csv', 'json', 'parquet').
        user_question: Specific transformation instructions.
    """
    tools = DataTools()
    sample_preview = tools.transform_load_context(input_file_path)

    llm = get_llm("claude")
    prompt = f"""
            You are a Python Data Analyst who uses Pandas to analyze data. 
            You need to provide only the Pandas Code that will help to perform the right ETL operations on the data stored in the file: {input_file_path}
            as per the user's question. Do not provide any explanation or comments, only
            the code should be provided. The code should be in a format that can be executed 
            in a Python environment with Pandas installed. 
            Don't write anything else than Pandas Code. \n
            
            Create the Pandas Dataframe from the data stored in the file: {input_file_path} and then 
            write the code to transform and save the data at {output_folder}.
            Here's the user's question: {user_question}\n
            Here's the context of the data you will be analyzing: {sample_preview}\n
        """

    response = llm.invoke(prompt).content
    pandas_code = response.strip().strip('```').strip().lstrip('python').strip()
    execution_result = tools.execute_code(pandas_code)

    return (
        f"Data transformed and saved at {output_folder} in {output_format} format.\n\n"
        f"Pandas Code Executed:\n{pandas_code}\n\n"
        f"Execution Result:\n{execution_result}"
    )


tools = [extract_load_tool, transform_load_tool]
llm = get_llm("claude")
llm_with_tools = llm.bind_tools(tools)


def llm_node(state: ETLAgentSchema):
    """Processes the conversation state and decides whether to invoke tools or finalize."""
    prompt = f"""
            You are a Python Data Analyst with access to ETL tools.
            Review the user request and invoke appropriate extraction/transformation tools.
            Once all tasks are completed, provide a clear confirmation.
            Chat history: {state.messages}\n
    """
    response = llm_with_tools.invoke(prompt)
    state.messages = state.messages + [response]
    return state


def tool_node(state: ETLAgentSchema):
    """Dispatches requested tool calls and appends results to conversation history."""
    tools_by_name = {t.name: t for t in tools}
    tool_messages = []

    for call in state.messages[-1].tool_calls:
        tool_fn = tools_by_name[call['name']]
        result = tool_fn.invoke(call['args'])
        tool_messages.append(ToolMessage(content=result, tool_call_id=call['id']))

    state.messages = state.messages + tool_messages
    return state


def should_continue(state: ETLAgentSchema) -> str:
    # Route to tool execution if the model produced any tool calls
    return "tool_node" if state.messages[-1].tool_calls else "end"


# Build the ETL execution graph
etl_agent_graph = StateGraph(ETLAgentSchema)
etl_agent_graph.add_node("llm_node", llm_node)
etl_agent_graph.add_node("tool_node", tool_node)

etl_agent_graph.add_edge(START, "llm_node")
etl_agent_graph.add_conditional_edges(
    "llm_node",
    should_continue,
    {"tool_node": "tool_node", "end": END}
)
etl_agent_graph.add_edge("tool_node", "llm_node")

etl_agent = etl_agent_graph.compile()
etl_analyst = etl_agent


if __name__ == "__main__":
    try:
        from IPython.display import Image
        img = Image(etl_agent.get_graph().draw_mermaid_png())
        with open("etl_agent_graph.png", "wb") as f:
            f.write(img.data)
    except Exception as e:
        print(f"Could not render graph image: {e}")

    sample_query = "I want to extract data from 'https://pokeapi.co/api/v2/pokemon' and save it to data/extract in CSV format"
    response = etl_agent.invoke({"messages": [HumanMessage(content=sample_query)]})
    print(response)
