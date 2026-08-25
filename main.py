"""Entry point for executing queries through the Data Agent multi-agent graph."""

from agents.router_agent import router_agent
from langchain_core.messages import HumanMessage


if __name__ == "__main__":
    query = (
        "I want to extract the data from the API endpoint "
        "'https://pokeapi.co/api/v2/pokemon' and save it to data/extract folder in csv format"
    )

    response = router_agent.invoke(
        {
            "messages": [HumanMessage(content=query)],
            "route_response": ""
        }
    )

    print(response)
