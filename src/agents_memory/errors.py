from __future__ import annotations


class AgentsMemoryError(Exception):
    pass


class NotFoundError(AgentsMemoryError):
    """A requested project or memory entry does not exist."""
