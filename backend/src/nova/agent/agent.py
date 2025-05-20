# langchain_client.py
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI # Import Google LLM
from langchain_core.messages import HumanMessage

from src.nova.config import settings


async def main():
    # 1. Initialize the Google LLM
    try:
        print(f"Initializing Google LLM with model: {settings.GOOGLE_MODEL_NAME}")
        print(f"Google API Key: {settings.GOOGLE_API_KEY}")
        print(f"Google API Key Type: {type(settings.GOOGLE_API_KEY)}")
        llm = ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        # Test the LLM (optional, but good for early debugging)
        await llm.ainvoke("Hello!")
        print("Google LLM initialized successfully.")
    except Exception as e:
        print(f"Error initializing Google LLM. Ensure GOOGLE_API_KEY is valid and 'langchain-google-genai' is installed. Error: {e}")
        return

    # 2. Setup MultiServerMCPClient to connect to your FastMCP server
    print(f"Initializing MCP client for server at: {settings.GMAIL_MCP_SERVER_URL}")
    client = MultiServerMCPClient(
        {
            "GMail": {
                "url": settings.GMAIL_MCP_SERVER_URL,
                "transport": "streamable_http",
                "description": "My local FastMCP server with a greet tool"
            }
        }
    )

    # 3. Fetch tools from the FastMCP server
    mcp_tools = []
    try:
        print("Attempting to fetch tools from FastMCP server...")
        mcp_tools = await client.get_tools()

        if not mcp_tools:
            print(f"No tools were fetched from the FastMCP server at {settings.GMAIL_MCP_SERVER_URL}.")
            print("Please ensure your FastMCP server (fmcp_server.py) is running.")
            return

        print(f"\nSuccessfully fetched {len(mcp_tools)} tool(s):")
        for tool in mcp_tools:
            print(f"  - Name: {tool.name}")
            print(f"    Description: {tool.description}")
            print(f"    Args schema: {tool.args}")

    except Exception as e:
        print(f"Error connecting to FastMCP server or fetching tools: {e}")
        return

    # 4. Create a LangGraph agent with the fetched tools
    try:
        agent_executor = create_react_agent(llm, mcp_tools)
        print("\nLangGraph ReAct agent created successfully.")
    except Exception as e:
        print(f"Error creating LangGraph agent: {e}")
        return

    # 5. Use the Agent to interact with the 'greet' tool
    print("\n--- Interacting with the Agent ---")

    user_queries = [
        "Create a new e-mail draft to bob@gmail.com that contains the subject 'Hello from Nova' and the body 'This is a test e-mail from Nova'."
    ]

    for query in user_queries:
        print(f"\nUser query: \"{query}\"")
        try:
            response = await agent_executor.ainvoke({
                "messages": [HumanMessage(content=query)]
            })
            ai_response = response.get("messages", [])[-1].content if response.get("messages") else "No response content found."
            print(f"Agent's response: {ai_response}")
        except Exception as e:
            print(f"Error during agent invocation for query '{query}': {e}")

    # 6. Close the client session when done
    print("\nProcessing complete. MCP Client sessions are typically managed by the adapter or per-call.")

if __name__ == "__main__":
    # Make sure fmcp_server.py is running before you execute this client.
    # Required libraries: langchain, langchain-mcp-adapters, langchain-google-genai, langgraph
    # Install with: pip install langchain langchain-mcp-adapters langchain-google-genai langgraph
    # (and fastmcp for the server)
    asyncio.run(main())