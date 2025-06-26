"""
Nova System Prompt API Endpoints

FastAPI endpoints for managing system prompt content, backups, and restoration.
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from agent.chat_agent import clear_chat_agent_cache
from models.chat import SystemPromptResponse, SystemPromptUpdateRequest
from models.events import NovaEvent
from utils.redis_manager import publish
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/system-prompt", tags=["system-prompt"])

# Default prompt file path
DEFAULT_PROMPT_FILE = Path("agent/prompts/NOVA_SYSTEM_PROMPT.md")


def get_content_hash(content: str) -> str:
    """Get SHA-256 hash of content for deduplication."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def should_create_backup(current_content: str, backup_dir: Path) -> bool:
    """Check if backup is needed by comparing content hashes."""
    current_hash = get_content_hash(current_content)
    
    # Check if any existing backup has the same content
    if not backup_dir.exists():
        return True
        
    for backup_file in backup_dir.glob("prompt_*.bak"):
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            if get_content_hash(backup_content) == current_hash:
                logger.info("Backup skipped - identical content exists", extra={
                    "data": {"existing_backup": backup_file.name, "content_hash": current_hash}
                })
                return False  # Duplicate found, no backup needed
        except Exception as e:
            logger.warning("Failed to read backup file during deduplication check", extra={
                "data": {"backup_file": str(backup_file), "error": str(e)}
            })
            continue  # Skip corrupted files
    
    return True  # No duplicate found, create backup


@router.post("/clear-cache")
async def clear_prompt_cache():
    """Clear the chat agent cache to force recreation with updated prompt."""
    clear_chat_agent_cache()
    return {"message": "Chat agent cache cleared - will recreate with updated prompt"}


@router.get("", response_model=SystemPromptResponse)
async def get_system_prompt():
    """Get the current system prompt content."""
    try:
        prompt_file = Path("agent/prompts/NOVA_SYSTEM_PROMPT.md")
        if not prompt_file.exists():
            raise HTTPException(status_code=404, detail="System prompt file not found")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        stats = prompt_file.stat()
        
        return SystemPromptResponse(
            content=content,
            file_path=str(prompt_file),
            last_modified=datetime.fromtimestamp(stats.st_mtime).isoformat(),
            size_bytes=stats.st_size
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error("Failed to read system prompt", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to read system prompt: {str(e)}")


@router.put("", response_model=SystemPromptResponse)
async def update_system_prompt(request: SystemPromptUpdateRequest):
    """Update the system prompt content and clear agent cache."""
    try:
        prompt_file = Path("agent/prompts/NOVA_SYSTEM_PROMPT.md")
        
        # Create backup directory relative to prompt file (consistent with config backups)
        backup_dir = prompt_file.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Only create backup if content is different from existing backups
            if should_create_backup(current_content, backup_dir):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"prompt_{timestamp}.bak"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(current_content)
                logger.info("Created prompt backup", extra={"data": {"backup_file": str(backup_file)}})
            else:
                logger.info("Skipped backup creation - identical content already exists")
        
        # Write new content
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        stats = prompt_file.stat()
        
        # Clear agent cache to force recreation with new prompt
        clear_chat_agent_cache()
        
        # Publish event for real-time updates
        event = NovaEvent(
            id=f"prompt_update_{datetime.now().isoformat()}",
            type="prompt_updated",
            timestamp=datetime.now(),
            data={
                "prompt_file": str(prompt_file),
                "change_type": "manual_update",
                "size_bytes": stats.st_size
            },
            source="chat-api"
        )
        await publish(event)
        
        logger.info("System prompt updated", extra={"data": {
            "file_path": str(prompt_file),
            "size_bytes": stats.st_size,
            "updated_by": "chat_api"
        }})
        
        return SystemPromptResponse(
            content=request.content,
            file_path=str(prompt_file),
            last_modified=datetime.fromtimestamp(stats.st_mtime).isoformat(),
            size_bytes=stats.st_size
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error("Failed to update system prompt", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to update system prompt: {str(e)}")


@router.get("/backups")
async def list_prompt_backups():
    """List available system prompt backups."""
    try:
        prompt_file = Path("agent/prompts/NOVA_SYSTEM_PROMPT.md")
        backup_dir = prompt_file.parent / "backups"
        if not backup_dir.exists():
            return {"backups": []}
        
        backups = []
        for backup_file in backup_dir.glob("prompt_*.bak"):
            stats = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "created": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                "size_bytes": stats.st_size
            })
        
        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created"], reverse=True)
        
        return {"backups": backups}
    except Exception as e:
        logger.error("Failed to list prompt backups", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@router.delete("/backups/{backup_filename}")
async def delete_prompt_backup(backup_filename: str):
    """Delete a specific backup file."""
    try:
        prompt_file = Path("agent/prompts/NOVA_SYSTEM_PROMPT.md")
        backup_dir = prompt_file.parent / "backups"
        backup_file = backup_dir / backup_filename
        
        # Validate filename format for security
        if not backup_filename.startswith("prompt_") or not backup_filename.endswith(".bak"):
            raise HTTPException(status_code=400, detail="Invalid backup filename format")
        
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        backup_file.unlink()  # Delete the file
        
        logger.info("Deleted prompt backup", extra={"data": {"backup_file": backup_filename}})
        return {"message": f"Backup {backup_filename} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete backup", extra={"data": {"error": str(e)}})
        raise HTTPException(status_code=500, detail=f"Failed to delete backup: {str(e)}")


@router.post("/restore/{backup_filename}")
async def restore_prompt_backup(backup_filename: str):
    """Restore system prompt from a backup file and clear agent cache."""
    try:
        prompt_file = Path("agent/prompts/NOVA_SYSTEM_PROMPT.md")
        backup_dir = prompt_file.parent / "backups"
        backup_file = backup_dir / backup_filename
        
        if not backup_file.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Validate filename format for security
        if not backup_filename.startswith("prompt_") or not backup_filename.endswith(".bak"):
            raise HTTPException(status_code=400, detail="Invalid backup filename format")
        
        # Read backup content
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_content = f.read()
        
        # Create backup of current version before restoring (only if different)
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Only create backup if current content is different from existing backups
            if should_create_backup(current_content, backup_dir):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                current_backup = backup_dir / f"prompt_{timestamp}_pre_restore.bak"
                with open(current_backup, 'w', encoding='utf-8') as f:
                    f.write(current_content)
                logger.info("Created pre-restore backup", extra={"data": {"backup_file": str(current_backup)}})
            else:
                logger.info("Skipped pre-restore backup - identical content already exists")
        
        # Restore from backup
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(backup_content)
        
        stats = prompt_file.stat()
        
        # Clear agent cache to force recreation with restored prompt
        clear_chat_agent_cache()
        
        # Publish event for real-time updates
        event = NovaEvent(
            id=f"prompt_restore_{datetime.now().isoformat()}",
            type="prompt_updated",
            timestamp=datetime.now(),
            data={
                "prompt_file": str(prompt_file),
                "change_type": "restore_backup",
                "backup_file": backup_filename,
                "size_bytes": stats.st_size
            },
            source="chat-api"
        )
        await publish(event)
        
        logger.info("System prompt restored from backup", extra={"data": {
            "backup_file": backup_filename,
            "restored_to": str(prompt_file)
        }})
        
        return SystemPromptResponse(
            content=backup_content,
            file_path=str(prompt_file),
            last_modified=datetime.fromtimestamp(stats.st_mtime).isoformat(),
            size_bytes=stats.st_size
        )
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        logger.error("Failed to restore prompt backup", extra={"data": {
            "backup_filename": backup_filename,
            "error": str(e)
        }})
        raise HTTPException(status_code=500, detail=f"Failed to restore backup: {str(e)}")