# Nova Chat Cleanup Scripts

This directory contains utility scripts for managing chat data in Nova to prevent database growth during development and testing.

## 🧹 Chat Cleanup Script (`cleanup_chats.py`)

Comprehensive cleanup of chat conversations from both the PostgreSQL checkpointer (LangGraph state) and Nova database tables.

### Usage

```bash
# Show current statistics
python scripts/cleanup_chats.py --list

# Clean everything (interactive confirmation)
python scripts/cleanup_chats.py --all

# Clean only checkpointer data
python scripts/cleanup_chats.py --checkpointer

# Clean only Nova database tables
python scripts/cleanup_chats.py --database

# Clean specific thread
python scripts/cleanup_chats.py --thread "chat-123456"

# Clean specific chat from database
python scripts/cleanup_chats.py --chat "uuid-here"

# Verbose output
python scripts/cleanup_chats.py --list --verbose
```

### What it cleans

1. **Checkpointer Tables** (LangGraph state):
   - `checkpoints` - Conversation state snapshots
   - `checkpoint_writes` - Pending writes
   - `checkpoint_blobs` - Serialized data

2. **Nova Database Tables**:
   - `chats` - Chat conversation records
   - `chat_messages` - Individual messages

### Features

- 📊 **Statistics** - Shows current data counts before cleanup
- 🔍 **Thread Detection** - Automatically finds all conversation threads
- ✅ **Safe Deletion** - Uses proper LangGraph deletion methods
- 🎯 **Selective Cleanup** - Can target specific threads or chats
- ⚠️ **Interactive Confirmation** - Prevents accidental data loss

## 🧪 Test Integration

The cleanup functionality is automatically integrated into the test suite to prevent database growth during test runs.

### Automatic Cleanup

All tests automatically clean up any checkpointer threads created during execution:

```python
# Tests automatically clean up after themselves
async def test_chat_functionality():
    # This test can create chat threads
    # They will be automatically cleaned up after the test
    pass
```

### Manual Control

For tests that need specific cleanup behavior:

```python
# Test with completely clean state
async def test_fresh_start(clean_slate_checkpointer):
    # Guaranteed clean checkpointer before and after
    pass

# Test with manual cleanup control
from tests.test_cleanup import CheckpointerCleaner

async def test_with_context():
    async with CheckpointerCleaner(clean_all=True) as cleaner:
        # Test runs here
        pass  # Automatic cleanup when context exits
```

## 🚀 Integration with CI/CD

Add to your CI pipeline to prevent test data accumulation:

```yaml
# .github/workflows/test.yml
- name: Clean test data
  run: python scripts/cleanup_chats.py --all --non-interactive
```

## 📊 Monitoring Database Growth

Use the list command regularly to monitor database size:

```bash
# Check current state
python scripts/cleanup_chats.py --list

# Example output:
# 📋 Checkpointer (LangGraph State):
#    - Total checkpoints: 142
#    - Unique threads: 25
# 🗄️ Nova Database:
#    - Total chats: 0
#    - Total messages: 0
```

## ⚠️ Important Notes

1. **Production Safety** - These scripts are designed for development/testing environments
2. **Backup First** - Always backup production data before running cleanup
3. **Database URL** - Uses `DATABASE_URL` environment variable or defaults to dev settings
4. **Thread Safety** - Safe to run while chat agents are active (they create new threads as needed)

## 🔧 Troubleshooting

### Common Issues

**Import Errors**: Ensure you're running from the project root:
```bash
# Correct
cd /root/nova
python scripts/cleanup_chats.py --list

# Incorrect  
cd scripts
python cleanup_chats.py --list
```

**Permission Errors**: Check database connection:
```bash
# Test connection
python -c "import os; print(os.getenv('DATABASE_URL', 'Using default'))"
```

**Large Cleanup Times**: For very large datasets, use targeted cleanup:
```bash
# Clean in batches
python scripts/cleanup_chats.py --checkpointer
python scripts/cleanup_chats.py --database
``` 