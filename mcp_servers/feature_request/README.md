# Feature Request MCP Server

An intelligent MCP server that allows Nova to create and manage feature requests in Linear when she encounters limitations or needs new capabilities.

## Overview

This MCP server provides Nova with the ability to automatically create well-structured feature requests in Linear when she encounters limitations while helping users. The server uses AI (Gemini Flash) to analyze requests against existing Linear issues and intelligently decides whether to create new issues or update existing ones.

## Features

- **Intelligent Analysis**: Uses Gemini Flash to analyze feature requests against existing Linear issues
- **Smart Decision Making**: Automatically decides whether to create new issues or update existing ones
- **Well-Structured Issues**: Creates Linear issues with proper problem statements, requirements, and acceptance criteria
- **Context Awareness**: Considers existing open/in-progress issues to avoid duplication
- **Error Handling**: Graceful fallbacks when AI analysis fails
- **Nova-Focused**: Tool description and interface designed specifically for Nova's perspective

## Tool: `request_feature`

The server provides one main tool for Nova:

### `request_feature(request: str)`

Use this tool when you encounter limitations or need new capabilities that prevent you from helping users effectively.

**When to use this:**
- You can't complete a user's request due to missing functionality
- You discover bugs or limitations in existing tools
- You need new integrations or capabilities
- Current workflows are inefficient and could be improved

**How to write a good feature request:**
- Describe the PROBLEM: What limitation are you facing? What can't you do?
- Explain the CONTEXT: What were you trying to accomplish for the user?
- Specify REQUIREMENTS: What exactly do you need to solve this?
- Include IMPACT: How would this help you serve users better?

**Example:**
```
"I cannot create calendar events with multiple attendees because the current tool only accepts a single attendee. I was trying to help a user schedule a team meeting but had to ask them to add attendees manually. I need the create_calendar_event tool to accept a list of email addresses for attendees so I can fully automate meeting creation."
```

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Linear API Configuration
LINEAR_API_KEY=your_linear_api_key_here
LINEAR_API_URL=https://api.linear.app/graphql

# Google AI Configuration  
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL_NAME=gemini-1.5-flash

# Optional: Server Configuration
HOST=127.0.0.1
PORT=8003
```

### API Keys

1. **Linear API Key**: Get from Linear Settings → API → Personal API Keys
2. **Google API Key**: Get from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Nova Integration

Add to your `configs/mcp_servers.yaml`:

```yaml
feature-request:
  url: http://127.0.0.1:8003/mcp
  description: "Feature Request Management for Linear"
  enabled: false  # Set to true once API keys are configured
```

## Architecture

### Core Components

1. **LinearClient**: GraphQL API client for Linear operations
   - Fetches open/in-progress issues for context
   - Creates new issues with automatic team assignment
   - Updates existing issues

2. **FeatureRequestAnalyzer**: AI-powered analysis using Gemini Flash
   - Analyzes requests against existing issues
   - Decides create vs update actions
   - Generates structured issue content
   - Handles JSON parsing and error fallbacks

3. **MCP Tool**: FastMCP-based `request_feature` tool
   - Nova-focused interface and documentation
   - Comprehensive error handling
   - Structured response format

### Workflow

1. Nova calls `request_feature` with a detailed problem description
2. Server fetches current open/in-progress Linear issues for context
3. Gemini Flash analyzes the request and decides:
   - **Create**: New issue needed for genuinely new functionality
   - **Update**: Existing issue should be enhanced with new requirements
4. Server executes the action in Linear
5. Returns structured response with issue details and URLs

## Development

### Installation

```bash
cd mcp_servers/feature_request
uv sync
```

### Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test categories
uv run pytest tests/test_linear_client.py -v
uv run pytest tests/test_feature_analyzer.py -v  
uv run pytest tests/test_mcp_integration.py -v
```

### Running the Server

```bash
# Development mode
uv run python main.py --host 127.0.0.1 --port 8003

# Production mode (Docker)
docker build -t feature-request-mcp .
docker run -p 8003:8003 --env-file .env feature-request-mcp
```

## Health Monitoring

The server uses the standard MCP `tools/list` endpoint for health checks. Nova's MCP client automatically monitors server health and tool availability through this endpoint.

## Error Handling

- **Missing API Keys**: Returns clear error message with configuration instructions
- **Linear API Errors**: Gracefully handles authentication and network issues
- **AI Analysis Failures**: Falls back to creating new issues with basic formatting
- **Invalid JSON**: Robust parsing with fallback to simple issue creation

## Security

- API keys stored in environment variables
- No sensitive data in logs
- GraphQL queries use parameterized inputs to prevent injection
- Backup filename validation prevents path traversal

## Performance

- Limits existing issues context to 10 most recent to prevent token overflow
- Async operations throughout for optimal performance
- Caching considerations for production deployment

## Future Enhancements

- Support for multiple Linear workspaces
- Custom priority and label assignment rules
- Integration with Nova's task management system
- Webhook support for real-time Linear updates 