from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()


def get_llm(level: str):
    """
    Returns the appropriate LLM instance based on complexity level.

    Args:
        level: Task complexity - 'low', 'medium', 'high', or 'claude'.
    """
    level_lower = level.lower()
    if level_lower == "low":
        return ChatOpenAI(
            model_name="gpt-5.6-luna",
            temperature=0,
            model_kwargs={"reasoning_effort": "none"}
        )
    elif level_lower == "medium":
        return ChatOpenAI(
            model_name="gpt-5.6-terra",
            temperature=0,
            model_kwargs={"reasoning_effort": "none"}
        )
    elif level_lower == "high":
        return ChatOpenAI(
            model_name="gpt-5.6-sol",
            temperature=0,
            model_kwargs={"reasoning_effort": "none"}
        )
    elif level_lower == "claude":
        return ChatAnthropic(model_name="claude-sonnet-5")
    else:
        raise ValueError(f"Unsupported model tier: {level}")


pick_llm = get_llm


if __name__ == "__main__":
    llm = get_llm("low")
    print(llm.invoke("What is the capital of France?"))
