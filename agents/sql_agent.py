import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.model_provider import get_llm, pick_llm
from utils.db_manager import DatabaseManager, DatabaseUtil
from models.schemas import AgentSchema, JudgeSchema
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END


def curate_ques(state: AgentSchema) -> AgentSchema:
    """Refines and clarifies the user's natural language question."""
    llm = get_llm("low")
    response = llm.invoke(f"Curate the following question: {state.user_question}").content
    state.curated_ques = response
    state.messages = state.messages + [HumanMessage(content=response)]
    return state


def prompt_query_context(state: AgentSchema) -> AgentSchema:
    """Introspects schema details from PostgreSQL to provide context for query generation."""
    conn_details = {
        "host": os.environ.get("host", "localhost"),
        "port": int(os.environ.get("port", 5432)),
        "user": os.environ.get("user", "postgres"),
        "password": os.environ.get("password", "postgres"),
        "dbname": os.environ.get("database", "postgres"),
    }

    db = DatabaseManager(conn_details)
    schema_info = db.schema_details("public")

    state.prompt_query_context = f"""
    You are an SQL analyst agent. Your task is to convert the user's natural language 
    query into Postgres SQL query that can be executed on the database. You are provided 
    with the user's original query and the schema details of the database, including
    table names, column names, data types, and sample data for each table so that 
    you can understand the structure of the database and generate an accurate SQL query.
    Unless user explicitly asks for specific number of rows, always limit the output to 10 rows.
    Note - Just generate the SQL query without any explanation or additional text because
    this query will be executed directly on the database. So, the output should be SQL
    ready to be executed without any modifications.  
    
    User's Original Query: {state.curated_ques}

    Database Schema Details:
    {schema_info}
    """
    return state


def generate_sql(state: AgentSchema) -> AgentSchema:
    """Generates the PostgreSQL query using the curated question and schema context."""
    llm = get_llm("medium")
    state.generated_sql_query = llm.invoke(state.prompt_query_context).content
    return state


def is_safe_sql(state: AgentSchema) -> AgentSchema:
    """Evaluates whether the generated SQL query is strictly read-only and safe to execute."""
    llm = get_llm("medium")
    llm_judge = llm.with_structured_output(JudgeSchema)

    prompt = f"""
    You are an SQL Judge for data security. Your task is to determine whether the SQL query is 
    safe or not. The SQL query should only be used for data retrieval and should not modify the 
    database in any way. Neither the SQL query nor the prompt should contain any SQL commands that can modify the
    database, such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, or any other commands that can change
    the structure or content of the database. If the SQL query is safe, respond with 'Yes' otherwise respond with 
    'No'. Additionally, provide comments explaining your decision.
    Here's the SQL query to evaluate:
    {state.generated_sql_query}"""

    response = llm_judge.invoke(prompt).model_dump()
    state.is_safe = response['answer']
    state.comments = response['comments']
    return state


def canceled_sql(state: AgentSchema) -> AgentSchema:
    """Handles unsafe query rejection and informs the user."""
    state.final_answer = (
        f"The generated SQL query was deemed unsafe to execute. "
        f"The reason provided by the judge is: {state.comments}. "
        f"Therefore, the SQL query will not be executed."
    )
    state.messages = state.messages + [AIMessage(content=state.final_answer)]
    return state


def execute_sql(state: AgentSchema) -> AgentSchema:
    """Executes the approved SQL query against the target database."""
    conn_details = {
        "host": os.environ.get("host", "localhost"),
        "port": int(os.environ.get("port", 5432)),
        "user": os.environ.get("user", "postgres"),
        "password": os.environ.get("password", "postgres"),
        "dbname": os.environ.get("database", "postgres"),
    }

    db = DatabaseManager(conn_details)
    state.sql_query_execution_result = db.execute_sql(state.generated_sql_query)
    return state


def represent_final_answer(state: AgentSchema) -> AgentSchema:
    """Synthesizes the database query output into a concise natural language explanation."""
    llm = get_llm("low")
    prompt = f"""
    You are an SQL analyst agent. Your task is to provide a final answer to the user based on the
    execution result of the SQL query and the user's original question. The final answer should be
    concise, clear, and directly address the user's query. Avoid including any SQL code or technical
    details in the final answer. The final answer should be in a user-friendly format that is easy to
    understand. If the execution result is empty or does not provide a clear answer to the user's question, explain this in the final answer. \n
    Here is the execution result: {state.sql_query_execution_result} \n
    Here is the user's original question: {state.curated_ques}
    """

    response = llm.invoke(prompt).content
    state.final_answer = response
    state.messages = state.messages + [AIMessage(content=response)]
    return state


# Build the SQL execution graph
sql_agent_graph = StateGraph(AgentSchema)

sql_agent_graph.add_node("curate_ques", curate_ques)
sql_agent_graph.add_node("prompt_query_context", prompt_query_context)
sql_agent_graph.add_node("generate_sql", generate_sql)
sql_agent_graph.add_node("is_safe_sql", is_safe_sql)
sql_agent_graph.add_node("canceled_sql", canceled_sql)
sql_agent_graph.add_node("execute_sql", execute_sql)
sql_agent_graph.add_node("represent_final_answer", represent_final_answer)

sql_agent_graph.add_edge(START, "curate_ques")
sql_agent_graph.add_edge("curate_ques", "prompt_query_context")
sql_agent_graph.add_edge("prompt_query_context", "generate_sql")
sql_agent_graph.add_edge("generate_sql", "is_safe_sql")


def is_safe_sql_edge(state: AgentSchema) -> str:
    # Route execution based on safety validation
    return "execute_sql" if state.is_safe.lower() == "yes" else "canceled_sql"


sql_agent_graph.add_conditional_edges(
    "is_safe_sql",
    is_safe_sql_edge,
    {
        "execute_sql": "execute_sql",
        "canceled_sql": "canceled_sql"
    }
)

sql_agent_graph.add_edge("canceled_sql", END)
sql_agent_graph.add_edge("execute_sql", "represent_final_answer")
sql_agent_graph.add_edge("represent_final_answer", END)

sql_agent = sql_agent_graph.compile()
sql_analyst = sql_agent


if __name__ == "__main__":
    try:
        from IPython.display import Image
        img = Image(sql_agent.get_graph().draw_mermaid_png())
        with open("sql_agent_graph.png", "wb") as f:
            f.write(img.data)
    except Exception as e:
        print(f"Could not render graph image: {e}")

    sample_query = {
        "messages": [],
        "user_question": "What are the different types of Payment Methods we have in our database",
        "curated_ques": "",
        "prompt_query_context": "",
        "generated_sql_query": "",
        "is_safe": "No",
        "comments": "",
        "sql_query_execution_result": "",
        "final_answer": ""
    }

    result = sql_agent.invoke(sample_query)
    print("Final answer:", result['final_answer'])
