"""
Memory utilities - centralized agent memory management.
"""

import json
import logging
from typing import Optional, Dict

from core.db import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def save_memory(session_id: str, memory_type: str, content: str, metadata: Optional[Dict] = None) -> bool:
    """
    Save agent memory to persistent storage (SQLite database).
    
    Args:
        session_id: Unique session identifier
        memory_type: Type of memory (decision, reasoning, preference, api_call, error, cart_state, etc.)
        content: JSON string content to store
        metadata: Optional metadata dict for additional context
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        if conn is None:
            logger.warning(f"[MEMORY] Database connection failed for session {session_id}")
            return False
        
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO agent_memory (session_id, memory_type, content, metadata)
            VALUES (?, ?, ?, ?)
        """, (session_id, memory_type, content, json.dumps(metadata or {})))
        
        conn.commit()
        conn.close()
        
        logger.info(f"[MEMORY] Saved {memory_type} for session {session_id}")
        return True
    
    except Exception as e:
        logger.error(f"[MEMORY] Failed to save memory: {e}", exc_info=True)
        return False


def load_memory(session_id: str, memory_type: Optional[str] = None) -> list:
    """
    Load agent memory from persistent storage.
    
    Args:
        session_id: Session to load memory for
        memory_type: Optional filter by memory type
    
    Returns:
        List of memory entries
    """
    try:
        conn = get_db_connection()
        if conn is None:
            logger.warning(f"[MEMORY] Database connection failed for session {session_id}")
            return []
        
        cursor = conn.cursor()
        
        if memory_type:
            cursor.execute("""
                SELECT memory_type, content, metadata, created_at 
                FROM agent_memory 
                WHERE session_id = ? AND memory_type = ?
                ORDER BY created_at DESC
            """, (session_id, memory_type))
        else:
            cursor.execute("""
                SELECT memory_type, content, metadata, created_at 
                FROM agent_memory 
                WHERE session_id = ?
                ORDER BY created_at DESC
            """, (session_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        logger.info(f"[MEMORY] Loaded {len(results)} entries for session {session_id}")
        return results
    
    except Exception as e:
        logger.error(f"[MEMORY] Failed to load memory: {e}", exc_info=True)
        return []


def clear_memory(session_id: str) -> bool:
    """
    Clear all memory for a session.
    
    Args:
        session_id: Session to clear
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = get_db_connection()
        if conn is None:
            logger.warning(f"[MEMORY] Database connection failed for session {session_id}")
            return False
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM agent_memory WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"[MEMORY] Cleared all memory for session {session_id}")
        return True
    
    except Exception as e:
        logger.error(f"[MEMORY] Failed to clear memory: {e}", exc_info=True)
        return False
