"""Small safety helpers shared by Telegram handlers."""

import logging

MAX_USER_QUERY_LENGTH = 100
logger = logging.getLogger(__name__)


def get_user_query(value: str | None) -> str | None:
    """Normalize a text query and reject commands, blanks, and oversized input."""
    if not value:
        return None
    query = value.strip()
    if not query or query.startswith("/") or len(query) > MAX_USER_QUERY_LENGTH:
        return None
    return query


def log_user_action(action: str, query: str | None = None) -> None:
    """Log action metadata without user text, identifiers, or credentials."""
    logger.info("bot_action action=%s query_length=%s", action, len(query) if query else 0)
