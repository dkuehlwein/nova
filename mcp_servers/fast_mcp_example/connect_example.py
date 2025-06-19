import requests
import json
import uuid

# Configuration (same as before)
base_url = "http://127.0.0.1:9000"
mcp_endpoint = "/mcp/"
url = base_url + mcp_endpoint

common_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

session_id = None # Will be populated after initialization

# --- Step 1: Initialize Session (same as before) ---
init_params = {
    "protocolVersion": 1,
    "capabilities": {},
    "clientInfo": {
        "name": "MyPythonClient",
        "version": "0.1.0"
    }
}
init_payload = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": init_params,
    "id": f"init-{uuid.uuid4()}"
}

print("--- Step 1: Attempting Session Initialization ---")
print(f"POST to: {url}")
# ... (print headers and payload as before) ...
print("Headers:", json.dumps(common_headers, indent=2))
print("Payload:", json.dumps(init_payload, indent=2))

try:
    init_response = requests.post(url, headers=common_headers, json=init_payload, timeout=10)
    print(f"\nInitialization Status Code: {init_response.status_code}")
    # ... (print headers and process response as before) ...
    print("Initialization Response Headers:")
    for key, value in init_response.headers.items():
        print(f"  {key}: {value}")
        if key.lower() == "mcp-session-id":
            session_id = value
            print(f"    -> Captured Session ID: {session_id}")
    print("Initialization Response Body:")
    try:
        # The initial response might be empty or just SSE connection negotiation.
        # The actual JSON-RPC result for 'initialize' comes as an SSE event.
        print(init_response.text) # Print raw text to see any immediate SSE events
        if "event: message" in init_response.text and "data:" in init_response.text:
             print("\n(Note: 'initialize' result is usually in the first SSE event printed above)")
    except json.JSONDecodeError:
        print(init_response.text)

    if init_response.status_code >= 400:
        print("\nInitialization failed based on status code. Aborting.")
        exit()
except requests.exceptions.RequestException as e:
    print(f"\nInitialization request failed: {e}")
    exit()

if not session_id:
    print("\nFailed to obtain a session ID from the initialization step. Cannot proceed.")
    exit()

# --- Step 1b: Send notifications/initialized (same as before) ---
print("\n--- Step 1b: Sending notifications/initialized ---")
notif_payload = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
}
headers_with_session = common_headers.copy()
headers_with_session["Mcp-Session-Id"] = session_id

print(f"POST to: {url}")
# ... (print headers and payload as before) ...
print("Headers:", json.dumps(headers_with_session, indent=2))
print("Payload:", json.dumps(notif_payload, indent=2))
try:
    notif_response = requests.post(url, headers=headers_with_session, json=notif_payload, timeout=10)
    print(f"\nNotification Status Code: {notif_response.status_code}")
    print("Notification Response Body (raw):")
    print(notif_response.text)
    if notif_response.status_code >= 300:
        print("\nNotification/initialized step may have failed or was not processed as expected.")
except requests.exceptions.RequestException as e:
    print(f"\nNotification/initialized request failed: {e}")

# --- Step 2: List Available Tools ---
print("\n--- Step 2: Listing Available Tools ---")
list_tools_payload = {
    "jsonrpc": "2.0",
    "method": "tools/list", # The method to list tools
    "params": {},          # Usually no parameters needed for listing
    "id": f"list-tools-{uuid.uuid4()}"
}

print(f"POST to: {url}")
print("Headers (with session ID):")
print(json.dumps(headers_with_session, indent=2))
print("Payload:")
print(json.dumps(list_tools_payload, indent=2))

try:
    list_tools_response = requests.post(url, headers=headers_with_session, json=list_tools_payload, timeout=10)
    print(f"\nList Tools Status Code: {list_tools_response.status_code}")
    print("List Tools Response Headers:")
    for key, value in list_tools_response.headers.items():
        print(f"  {key}: {value}")
    print("List Tools Response Body:")
    try:
        list_tools_response_json = list_tools_response.json() # Expect JSON for this response
        print(json.dumps(list_tools_response_json, indent=2))
        if list_tools_response_json.get('jsonrpc') == '2.0':
            if 'error' in list_tools_response_json:
                print("\n--- JSON-RPC Error in List Tools ---")
                print(f"  Message: {list_tools_response_json['error'].get('message')}")
                print(f"  Code:    {list_tools_response_json['error'].get('code')}")
            elif 'result' in list_tools_response_json:
                print("\n--- JSON-RPC Success in List Tools ---")
                # The structure of 'result' will depend on how FastMCP returns the list
                # Typically it's an array of objects, where each object describes a tool.
                print(f"  Result: {json.dumps(list_tools_response_json['result'], indent=2)}")
                if isinstance(list_tools_response_json['result'], list):
                    print(f"\nFound {len(list_tools_response_json['result'])} tool(s):")
                    for tool_info in list_tools_response_json['result']:
                        tool_name = tool_info.get('name', 'N/A')
                        tool_description = tool_info.get('description', 'No description')
                        print(f"  - {tool_name}: {tool_description}")

    except json.JSONDecodeError:
        # If the direct response isn't JSON, it might be coming via SSE
        print("Raw List Tools Response Text (might be SSE):")
        print(list_tools_response.text)
        if "event: message" in list_tools_response.text and "data:" in list_tools_response.text:
            print("\n(Note: 'tools/list' result might be in an SSE event printed above)")


except requests.exceptions.RequestException as e:
    print(f"\nList tools request failed: {e}")


# --- Step 3: Call the 'greet' tool (same as before, now Step 3) ---
print("\n--- Step 3: Attempting 'greet' Tool Call ---")
tool_call_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "greet",
        "arguments": {
            "name": "User via Full Python Script"
        }
    },
    "id": f"tool-{uuid.uuid4()}"
}
# ... (rest of the 'greet' tool call logic as in your working script) ...
print(f"POST to: {url}")
print("Headers (with session ID):")
print(json.dumps(headers_with_session, indent=2))
print("Payload:")
print(json.dumps(tool_call_payload, indent=2))

try:
    tool_response = requests.post(url, headers=headers_with_session, json=tool_call_payload, timeout=10)
    print(f"\nTool Call Status Code: {tool_response.status_code}")
    print("Tool Call Response Headers:")
    for key, value in tool_response.headers.items():
        print(f"  {key}: {value}")
    print("Tool Call Response Body:")
    try:
        tool_response_json = tool_response.json()
        print(json.dumps(tool_response_json, indent=2))
        if tool_response_json.get('jsonrpc') == '2.0':
            if 'error' in tool_response_json:
                print("\n--- JSON-RPC Error in Tool Call ---")
                print(f"  Message: {tool_response_json['error'].get('message')}")
                print(f"  Code:    {tool_response_json['error'].get('code')}")
            elif 'result' in tool_response_json:
                print("\n--- JSON-RPC Success in Tool Call ---")
                print(f"  Result: {json.dumps(tool_response_json['result'], indent=2)}")
    except json.JSONDecodeError:
        print(tool_response.text)

except requests.exceptions.RequestException as e:
    print(f"\nTool call request failed: {e}")


"""
Output:
daniel@CE42696:/mnt/c/Users/dkuehlwe/PycharmProjects/nova/nova/mcp_servers/fast_mcp_example$ uv run test_,main.py 
--- Step 1: Attempting Session Initialization ---
POST to: http://127.0.0.1:9000/mcp/
Headers: {
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream"
}
Payload: {
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": 1,
    "capabilities": {},
    "clientInfo": {
      "name": "MyPythonClient",
      "version": "0.1.0"
    }
  },
  "id": "init-db0a2584-04c3-49fa-a841-353eb31fc580"
}

Initialization Status Code: 200
Initialization Response Headers:
  date: Tue, 20 May 2025 00:00:48 GMT
  server: uvicorn
  cache-control: no-cache, no-transform
  connection: keep-alive
  content-type: text/event-stream
  mcp-session-id: fd95b3613ec34a79833734caf597ea2b
    -> Captured Session ID: fd95b3613ec34a79833734caf597ea2b
  x-accel-buffering: no
  Transfer-Encoding: chunked
Initialization Response Body:
event: message
data: {"jsonrpc":"2.0","id":"init-db0a2584-04c3-49fa-a841-353eb31fc580","result":{"protocolVersion":"2025-03-26","capabilities":{"experimental":{},"prompts":{"listChanged":false},"resources":{"subscribe":false,"listChanged":false},"tools":{"listChanged":false}},"serverInfo":{"name":"MyServer","version":"1.9.0"}}}



(Note: 'initialize' result is usually in the first SSE event printed above)

--- Step 1b: Sending notifications/initialized ---
POST to: http://127.0.0.1:9000/mcp/
Headers: {
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream",
  "Mcp-Session-Id": "fd95b3613ec34a79833734caf597ea2b"
}
Payload: {
  "jsonrpc": "2.0",
  "method": "notifications/initialized",
  "params": {}
}

Notification Status Code: 202
Notification Response Body (raw):


--- Step 2: Listing Available Tools ---
POST to: http://127.0.0.1:9000/mcp/
Headers (with session ID):
{
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream",
  "Mcp-Session-Id": "fd95b3613ec34a79833734caf597ea2b"
}
Payload:
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": {},
  "id": "list-tools-1c693744-5583-4182-9a50-40caaa05aa40"
}

List Tools Status Code: 200
List Tools Response Headers:
  date: Tue, 20 May 2025 00:00:48 GMT
  server: uvicorn
  cache-control: no-cache, no-transform
  connection: keep-alive
  content-type: text/event-stream
  mcp-session-id: fd95b3613ec34a79833734caf597ea2b
  x-accel-buffering: no
  Transfer-Encoding: chunked
List Tools Response Body:
Raw List Tools Response Text (might be SSE):
event: message
data: {"jsonrpc":"2.0","id":"list-tools-1c693744-5583-4182-9a50-40caaa05aa40","result":{"tools":[{"name":"greet","description":"Greet a user by name.","inputSchema":{"properties":{"name":{"title":"Name","type":"string"}},"required":["name"],"type":"object"}}]}}



(Note: 'tools/list' result might be in an SSE event printed above)

--- Step 3: Attempting 'greet' Tool Call ---
POST to: http://127.0.0.1:9000/mcp/
Headers (with session ID):
{
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream",
  "Mcp-Session-Id": "fd95b3613ec34a79833734caf597ea2b"
}
Payload:
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "greet",
    "arguments": {
      "name": "User via Full Python Script"
    }
  },
  "id": "tool-504a1899-998c-4d02-bc5f-03f2261bb8f0"
}

Tool Call Status Code: 200
Tool Call Response Headers:
  date: Tue, 20 May 2025 00:00:48 GMT
  server: uvicorn
  cache-control: no-cache, no-transform
  connection: keep-alive
  content-type: text/event-stream
  mcp-session-id: fd95b3613ec34a79833734caf597ea2b
  x-accel-buffering: no
  Transfer-Encoding: chunked
Tool Call Response Body:
event: message
data: {"jsonrpc":"2.0","id":"tool-504a1899-998c-4d02-bc5f-03f2261bb8f0","result":{"content":[{"type":"text","text":"Hello, User via Full Python Script!"}],"isError":false}}
"""