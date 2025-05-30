# langchain_client.py
import asyncio
import os 
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI # Import Google LLM
from langchain_core.messages import HumanMessage

from src.nova.config import settings
from src.nova.mcp_client import mcp_manager


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

    # 1. Initialize the Google LLM
    try:
        print(f"Initializing Google LLM with model: {settings.GOOGLE_MODEL_NAME}")
        llm = ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        print("Google LLM initialized successfully.")
    except Exception as e:
        print(f"Error initializing Google LLM. Ensure GOOGLE_API_KEY is valid and 'langchain-google-genai' is installed. Error: {e}")
        return

    # 2. Initialize MCP client and get tools
    client, mcp_tools = await mcp_manager.get_client_and_tools()
    
    if not client or not mcp_tools:
        print("❌ Failed to initialize MCP client or fetch tools. Cannot proceed.")
        return

    # 3. Create a LangGraph agent with the fetched tools
    try:
        agent_executor = create_react_agent(llm, mcp_tools)
        print(f"\n🤖 LangGraph ReAct agent created successfully with {len(mcp_tools)} tools.")
    except Exception as e:
        print(f"❌ Error creating LangGraph agent: {e}")
        return

    # 4. Use the Agent to interact with MCP tools
    print("\n--- 🚀 Interacting with the Agent ---")

    user_queries = [
        #"Send an email to John Doe at daniel.kuehlwein@gmail.com with the subject 'Test Email from Agent' and body 'This is a test email sent from the Nova agent.'.",
        "Create a new task in the 'Todo' lane with the title 'Test Task' and content 'This is a test task'.",
    ]

    # If tasks server is working, add task-related queries
    working_server_names = [server["name"] for server in mcp_manager.working_servers]
    if "tasks" in working_server_names:
        user_queries.append("List all tasks across all lanes to see what's currently in the system.")
    else:
        print("  💡 Tasks server not available - skipping task-related queries")

    for query in user_queries:
        print(f"\n📝 User query: \"{query}\"")
        try:
            response = await agent_executor.ainvoke({
                "messages": [HumanMessage(content=query)]
            })
            ai_response = response.get("messages", [])[-1].content if response.get("messages") else "No response content found."
            print(f"🤖 Agent's response: {ai_response}")
        except Exception as e:
            print(f"❌ Error during agent invocation for query '{query}': {e}")
            import traceback
            print("Detailed error:")
            traceback.print_exc()

    print("\n✅ Processing complete.")

if __name__ == "__main__":
    # Make sure at least one MCP server is running before you execute this client.
    # Required libraries: langchain, langchain-mcp-adapters, langchain-google-genai, langgraph
    # Install with: pip install langchain langchain-mcp-adapters langchain-google-genai langgraph
    # (and fastmcp for the server)
    asyncio.run(main())