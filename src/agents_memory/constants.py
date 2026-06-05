from __future__ import annotations

VALID_TYPES = {"instruction", "learning", "observation", "decision"}
VALID_STATUSES = {"active", "retired", "superseded"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_AGENTS = {"codex", "claude", "opencode", "dashboard", "unknown"}
SUPPORTED_SETUP_AGENTS = {"codex", "claude", "opencode"}

STATUS_ORDER = {
    "active": 0,
    "superseded": 1,
    "retired": 2,
}
TYPE_ORDER = {
    "instruction": 0,
    "decision": 1,
    "learning": 2,
    "observation": 3,
}
PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2,
}
