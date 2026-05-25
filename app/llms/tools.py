from langchain_core.tools import tool

# Placeholder for tools as requested by the user.
# "the tools will be integrated later"

@tool
def dummy_tool(query: str) -> str:
    """A dummy tool to satisfy LangChain tool bindings if needed."""
    return f"Dummy response for {query}"

def get_available_tools() -> list:
    """
    Returns the list of tools available for the LLM to use during translation.
    """
    return []
