# langchain_client.py
import asyncio
import os 
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI # Import Google LLM
from langchain_core.messages import HumanMessage

from src.nova.config import settings


async def main():
    # 0. Configure LangSmith (if enabled)
    if settings.USE_LANGSMITH:
        # Ensure LangSmith environment variables are set
        os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2 or "true"
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"
        if settings.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY.get_secret_value()
        if settings.LANGCHAIN_PROJECT:
            os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        print("LangSmith tracing is ENABLED.")
        print(f"  LANGCHAIN_TRACING_V2: {os.environ.get('LANGCHAIN_TRACING_V2')}")
        print(f"  LANGCHAIN_ENDPOINT: {os.environ.get('LANGCHAIN_ENDPOINT')}")
        print(f"  LANGCHAIN_PROJECT: {os.environ.get('LANGCHAIN_PROJECT')}")
        print(f"  LANGCHAIN_API_KEY is set: {bool(os.environ.get('LANGCHAIN_API_KEY'))}")
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        print("LangSmith tracing is DISABLED.")

    """
    # 1. Initialize the Google LLM
    try:
        print(f"Initializing Google LLM with model: {settings.GOOGLE_MODEL_NAME}")
        print(f"Google API Key: {settings.GOOGLE_API_KEY}")
        print(f"Google API Key Type: {type(settings.GOOGLE_API_KEY)}")
        llm = ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        print("Google LLM initialized successfully.")
    except Exception as e:
        print(f"Error initializing Google LLM. Ensure GOOGLE_API_KEY is valid and 'langchain-google-genai' is installed. Error: {e}")
        return
    #"""

    # 2. Setup MultiServerMCPClient to connect to all active MCP servers
    active_servers = settings.active_mcp_servers
    enabled_servers = settings.enabled_mcp_servers
    
    print(f"Found {len(active_servers)} configured MCP servers: {list(active_servers.keys())}")
    print(f"Enabled servers: {enabled_servers}")
    
    # Prepare server configuration for MultiServerMCPClient
    server_config = {}
    for server_name, server_info in active_servers.items():
        if server_info["url"]:  # Only include servers with valid URLs
            server_config[server_name.title()] = {
                "url": server_info["url"],
                "transport": server_info["transport"],
                "description": server_info["description"]
            }
            print(f"  - {server_name.title()}: {server_info['url']}")
        else:
            print(f"  - {server_name.title()}: DISABLED (no URL configured)")
    
    if not server_config:
        print("No MCP servers are configured and enabled. Please check your configuration.")
        return
    
    client = MultiServerMCPClient(server_config)

    # 3. Fetch tools from all configured MCP servers
    mcp_tools = []
    try:
        print(f"\nAttempting to fetch tools from {len(server_config)} MCP server(s)...")
        mcp_tools = await client.get_tools()

        if not mcp_tools:
            print("No tools were fetched from any MCP servers.")
            print("Please ensure your MCP servers are running and accessible.")
            return

        print(f"\nSuccessfully fetched {len(mcp_tools)} tool(s) total:")
        for tool in mcp_tools:
            print(f"  - Name: {tool.name}")
            print(f"    Description: {tool.description}")
            print(f"    Args schema: {tool.args}")

    except Exception as e:
        print(f"Error connecting to MCP servers or fetching tools: {e}")
        print("This might indicate that one or more MCP servers are not running.")
        print(f"Configured servers: {list(server_config.keys())}")
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