import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.sql_agent import sql_agent, sql_analyst
from agents.etl_agent import etl_agent, etl_analyst
from utils.model_provider import get_llm, pick_llm
from utils.data_tools import DataTools, ETLTools
from models.schemas import RouterSchema, DataAgentSchema
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END


llm = get_llm("claude")
llm_router = llm.with_structured_output(RouterSchema)


def router_node(state: DataAgentSchema):
    """Classifies user intent to determine whether the request is SQL- or ETL-focused."""
    latest_message = state.messages[-1].content
    decision = llm_router.invoke(latest_message).model_dump()
    state.route_response = decision['answer']
    return state


def etl_node(state: DataAgentSchema):
    """Delegates query processing to the ETL agent."""
    latest_message = state.messages[-1].content
    response = etl_agent.invoke({"messages": [HumanMessage(content=latest_message)]})
    state.messages = state.messages + [response]
    return state


def sql_node(state: DataAgentSchema):
    """Initializes SQL state and delegates execution to the SQL analyst agent."""
    latest_message = state.messages[-1].content
    sql_input = {
        "messages": [],
        "user_question": latest_message,
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }
    response = sql_agent.invoke(sql_input)
    state.messages = state.messages + [response]
    return state


def route_edge(state: DataAgentSchema) -> str:
    # Route execution based on classified query type
    if state.route_response == "sql":
        return "sql_node"
    elif state.route_response == "etl":
        return "etl_node"
    raise ValueError(f"Unknown route response: {state.route_response}")


# Build the supervisor router graph
data_agent_graph = StateGraph(DataAgentSchema)
data_agent_graph.add_node("router_node", router_node)
data_agent_graph.add_node("etl_node", etl_node)
data_agent_graph.add_node("sql_node", sql_node)

data_agent_graph.add_edge(START, "router_node")
data_agent_graph.add_conditional_edges(
    "router_node",
    route_edge,
    {
        "sql_node": "sql_node",
        "etl_node": "etl_node"
    }
)

router_agent = data_agent_graph.compile()
data_agent = router_agent


if __name__ == "__main__":
    try:
        from IPython.display import Image
        img = Image(router_agent.get_graph().draw_mermaid_png())
        with open("router_agent_graph.png", "wb") as f:
            f.write(img.data)
    except Exception as e:
        print(f"Could not render graph image: {e}")

    sample_query = (
        "I want to extract data from 'https://pokeapi.co/api/v2/pokemon' "
        "and save it to data/extract in CSV format"
    )
    result = router_agent.invoke({
        "messages": [HumanMessage(content=sample_query)],
        "route_response": ""
    })
    print(result)
