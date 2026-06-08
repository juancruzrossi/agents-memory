VALID_TYPES = {"instruction", "decision", "observation"}
VALID_STATUSES = {"active", "archived"}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_AGENTS = {"codex", "claude", "opencode", "dashboard", "unknown"}
SUPPORTED_SETUP_AGENTS = {"codex", "claude", "opencode"}

STATUS_ORDER = {
    "active": 0,
    "archived": 1,
}
TYPE_ORDER = {
    "instruction": 0,
    "decision": 1,
    "observation": 2,
}
PRIORITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2,
}
