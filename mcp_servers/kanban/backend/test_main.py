#!/usr/bin/env python3

import requests
import json
import uuid
import time
import os
import shutil

# Configuration
base_url = "http://127.0.0.1:8002"
mcp_endpoint = "/mcp/"
url = base_url + mcp_endpoint

common_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

session_id = None  # Will be populated after initialization

def print_separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_step(step_num, description):
    print(f"\n--- Step {step_num}: {description} ---")

def print_response(response, description="Response"):
    print(f"\n{description} Status Code: {response.status_code}")
    print(f"{description} Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    print(f"{description} Body:")
    try:
        response_json = response.json()
        print(json.dumps(response_json, indent=2))
        return response_json
    except json.JSONDecodeError:
        print(response.text)
        return None

def make_request(payload, description="Request"):
    headers = common_headers.copy()
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    
    print(f"\nPOST to: {url}")
    print("Headers:")
    print(json.dumps(headers, indent=2))
    print("Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return print_response(response, description)
    except requests.exceptions.RequestException as e:
        print(f"\n{description} request failed: {e}")
        return None

print_separator("Kanban MCP Server Test Suite")

# --- Step 1: Health Check ---
print_step(1, "Health Check")
try:
    health_response = requests.get(f"{base_url}/health", timeout=5)
    print_response(health_response, "Health Check")
    if health_response.status_code != 200:
        print("❌ Health check failed! Is the server running?")
        exit(1)
    print("✅ Server is healthy!")
except requests.exceptions.RequestException as e:
    print(f"❌ Health check failed: {e}")
    print("Make sure the server is running with: python main.py --port 8003")
    exit(1)

# --- Step 2: Initialize Session ---
print_step(2, "Session Initialization")
init_params = {
    "protocolVersion": 1,
    "capabilities": {},
    "clientInfo": {
        "name": "KanbanTestClient",
        "version": "0.1.0"
    }
}
init_payload = {
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": init_params,
    "id": f"init-{uuid.uuid4()}"
}

init_response_json = make_request(init_payload, "Initialization")

# Extract session ID from headers
for key, value in requests.post(url, headers=common_headers, json=init_payload, timeout=10).headers.items():
    if key.lower() == "mcp-session-id":
        session_id = value
        print(f"    -> Captured Session ID: {session_id}")
        break

if not session_id:
    print("❌ Failed to obtain session ID. Cannot proceed.")
    exit(1)

# --- Step 3: Send notifications/initialized ---
print_step(3, "Send Initialized Notification")
notif_payload = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
}
make_request(notif_payload, "Initialized Notification")

# --- Step 4: List Available Tools ---
print_step(4, "List Available Tools")
list_tools_payload = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": f"list-tools-{uuid.uuid4()}"
}

tools_response = make_request(list_tools_payload, "List Tools")
if tools_response and 'result' in tools_response:
    tools = tools_response['result']
    print(f"\n✅ Found {len(tools)} tool(s):")
    for tool in tools:
        tool_name = tool.get('name', 'N/A')
        tool_description = tool.get('description', 'No description')
        print(f"  - {tool_name}: {tool_description}")

# Test variables
test_lane_1 = "Todo"
test_lane_2 = "In Progress"
test_task_title = "Test Task from Python Client"
test_task_content = "This is a test task created by the Python test client."
created_task_id = None

# --- Step 5: Create a Lane ---
print_step(5, "Create Lane")
create_lane_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "create_lane",
        "arguments": {
            "lane_name": test_lane_1
        }
    },
    "id": f"create-lane-{uuid.uuid4()}"
}

create_lane_response = make_request(create_lane_payload, "Create Lane")
if create_lane_response and 'result' in create_lane_response:
    print("✅ Lane created successfully!")

# --- Step 6: List Lanes ---
print_step(6, "List All Lanes")
list_lanes_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "list_lanes",
        "arguments": {}
    },
    "id": f"list-lanes-{uuid.uuid4()}"
}

list_lanes_response = make_request(list_lanes_payload, "List Lanes")
if list_lanes_response and 'result' in list_lanes_response:
    print("✅ Lanes listed successfully!")

# --- Step 7: Add a Task ---
print_step(7, "Add Task")
add_task_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "add_task",
        "arguments": {
            "title": test_task_title,
            "lane": test_lane_1,
            "content": test_task_content,
            "tags": ["test", "python", "automation"]
        }
    },
    "id": f"add-task-{uuid.uuid4()}"
}

add_task_response = make_request(add_task_payload, "Add Task")
if add_task_response and 'result' in add_task_response:
    print("✅ Task added successfully!")
    # Extract task ID from response
    try:
        result_text = add_task_response['result']
        if isinstance(result_text, str) and "Task added successfully" in result_text:
            # Parse the JSON from the result text
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                task_data = json.loads(json_match.group())
                created_task_id = task_data.get('id')
                print(f"    -> Task ID: {created_task_id}")
    except (json.JSONDecodeError, KeyError):
        print("    -> Could not extract task ID from response")

# --- Step 8: List All Tasks ---
print_step(8, "List All Tasks")
list_tasks_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "list_all_tasks",
        "arguments": {}
    },
    "id": f"list-tasks-{uuid.uuid4()}"
}

list_tasks_response = make_request(list_tasks_payload, "List All Tasks")
if list_tasks_response and 'result' in list_tasks_response:
    print("✅ Tasks listed successfully!")

# --- Step 9: Get Tasks from Specific Lane ---
print_step(9, "Get Lane Tasks")
get_lane_tasks_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "get_lane_tasks",
        "arguments": {
            "lane": test_lane_1
        }
    },
    "id": f"get-lane-tasks-{uuid.uuid4()}"
}

get_lane_tasks_response = make_request(get_lane_tasks_payload, "Get Lane Tasks")
if get_lane_tasks_response and 'result' in get_lane_tasks_response:
    print("✅ Lane tasks retrieved successfully!")

# --- Step 10: Get Specific Task (if we have a task ID) ---
if created_task_id:
    print_step(10, "Get Specific Task")
    get_task_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_task",
            "arguments": {
                "task_id": created_task_id,
                "lane": test_lane_1
            }
        },
        "id": f"get-task-{uuid.uuid4()}"
    }

    get_task_response = make_request(get_task_payload, "Get Task")
    if get_task_response and 'result' in get_task_response:
        print("✅ Task retrieved successfully!")

    # --- Step 11: Update Task Content ---
    print_step(11, "Update Task Content")
    update_task_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "update_task",
            "arguments": {
                "task_id": created_task_id,
                "content": f"{test_task_content}\n\nUpdated by test client at {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "lane": test_lane_1
            }
        },
        "id": f"update-task-{uuid.uuid4()}"
    }

    update_task_response = make_request(update_task_payload, "Update Task")
    if update_task_response and 'result' in update_task_response:
        print("✅ Task updated successfully!")

    # --- Step 12: Create Another Lane and Move Task ---
    print_step(12, "Create Second Lane")
    create_lane_2_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "create_lane",
            "arguments": {
                "lane_name": test_lane_2
            }
        },
        "id": f"create-lane-2-{uuid.uuid4()}"
    }

    create_lane_2_response = make_request(create_lane_2_payload, "Create Second Lane")
    if create_lane_2_response and 'result' in create_lane_2_response:
        print("✅ Second lane created successfully!")

    print_step(13, "Move Task Between Lanes")
    move_task_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "move_task",
            "arguments": {
                "task_id": created_task_id,
                "from_lane": test_lane_1,
                "to_lane": test_lane_2
            }
        },
        "id": f"move-task-{uuid.uuid4()}"
    }

    move_task_response = make_request(move_task_payload, "Move Task")
    if move_task_response and 'result' in move_task_response:
        print("✅ Task moved successfully!")

    # --- Step 14: Verify Task is in New Lane ---
    print_step(14, "Verify Task in New Lane")
    verify_lane_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_lane_tasks",
            "arguments": {
                "lane": test_lane_2
            }
        },
        "id": f"verify-lane-{uuid.uuid4()}"
    }

    verify_lane_response = make_request(verify_lane_payload, "Verify New Lane")
    if verify_lane_response and 'result' in verify_lane_response:
        print("✅ Task verified in new lane!")

    # --- Step 15: Delete Task ---
    print_step(15, "Delete Task")
    delete_task_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "delete_task",
            "arguments": {
                "task_id": created_task_id,
                "lane": test_lane_2
            }
        },
        "id": f"delete-task-{uuid.uuid4()}"
    }

    delete_task_response = make_request(delete_task_payload, "Delete Task")
    if delete_task_response and 'result' in delete_task_response:
        print("✅ Task deleted successfully!")

# --- Step 16: Clean Up - Delete Test Lanes ---
print_step(16, "Clean Up - Delete Test Lanes")
for lane in [test_lane_1, test_lane_2]:
    delete_lane_payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "delete_lane",
            "arguments": {
                "lane_name": lane
            }
        },
        "id": f"delete-lane-{uuid.uuid4()}"
    }

    delete_lane_response = make_request(delete_lane_payload, f"Delete Lane {lane}")
    if delete_lane_response and 'result' in delete_lane_response:
        print(f"✅ Lane {lane} deleted successfully!")

# --- Final Step: Verify Clean State ---
print_step(17, "Final Verification - List Remaining Lanes")
final_list_payload = {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "list_lanes",
        "arguments": {}
    },
    "id": f"final-list-{uuid.uuid4()}"
}

final_list_response = make_request(final_list_payload, "Final Lane List")
if final_list_response and 'result' in final_list_response:
    print("✅ Final verification complete!")

print_separator("Test Suite Complete!")
print("🎉 All Kanban MCP Server tests completed successfully!")
print("\nTo run this test again:")
print("1. Make sure the server is running: python main.py --port 8003")
print("2. Run this test: python test_main.py")
print("\nTo integrate with your agent:")
print("- Add the server URL to your agent configuration: http://127.0.0.1:8003/mcp/")
print("- Use the /health endpoint for health checks: http://127.0.0.1:8003/health") 