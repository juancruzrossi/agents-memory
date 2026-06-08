from __future__ import annotations

from typing import Any

from .constants import PRIORITY_ORDER, STATUS_ORDER, TYPE_ORDER


def _display_sort_key(entry: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        STATUS_ORDER[entry["status"]],
        TYPE_ORDER[entry["type"]],
        PRIORITY_ORDER[entry["priority"]],
        entry["id"],
    )


def format_entries_text(memory_view: dict[str, Any], *, include_all: bool) -> str:
    project = memory_view["project"]
    entries = memory_view["entries"]
    related_projects = memory_view["related_projects"]
    title = "All Project Memory Entries" if include_all else "Active Project Memory Entries"
    lines = [title, f"Project: {project['identity_kind']}:{project['identity_value']}"]
    if entries:
        append_entries(lines, sorted(entries, key=_display_sort_key))
    elif related_projects:
        lines.append("No memory entries found for the exact project.")
    else:
        lines.append("No memory entries found.")

    if related_projects:
        lines.append("")
        lines.append("Related Project Memory Entries")
        for related in related_projects:
            related_project = related["project"]
            lines.append("")
            identity = f"{related_project['identity_kind']}:{related_project['identity_value']}"
            lines.append(f"Project: {identity}")
            append_entries(lines, sorted(related["entries"], key=_display_sort_key))
    return "\n".join(lines)


def append_entries(lines: list[str], entries: list[dict[str, Any]]) -> None:
    current_group: tuple[str, str] | None = None
    for entry in entries:
        group = (entry["status"], entry["type"])
        if group != current_group:
            lines.append("")
            lines.append(f"{entry['status'].title()} {entry['type'].title()}s")
            current_group = group
        lines.append(f"- #{entry['id']} [{entry['priority']}] {entry['content']}")
        lines.append(f"  Reason: {entry['rationale']}")
        lines.append(f"  Agent: {entry['agent']} | Created: {entry['created_at']}")


def build_compact_view(entries: list[dict[str, Any]], budget: int) -> dict[str, Any]:
    sorted_entries = sorted(
        entries,
        key=lambda entry: (
            PRIORITY_ORDER[entry["priority"]],
            TYPE_ORDER[entry["type"]],
            entry["id"],
        ),
    )
    included: list[dict[str, Any]] = []
    omitted = 0
    used = 0
    for entry in sorted_entries:
        rendered = compact_entry_text(entry)
        next_used = used + len(rendered) + 1
        if next_used > budget:
            omitted += 1
            continue
        included.append(entry)
        used = next_used
    return {
        "entries": included,
        "omitted_count": omitted,
        "used_chars": used,
    }


def compact_entry_text(entry: dict[str, Any]) -> str:
    reason = f" Reason: {entry['rationale']}" if entry["rationale"] else ""
    return f"- [{entry['priority']}] {entry['content']}{reason}"


def format_startup_text(project: dict[str, Any], compact: dict[str, Any], budget: int) -> str:
    entries = compact["entries"]
    if not entries:
        return ""
    lines = [
        "Project Memory",
        f"Source: ~/.agents-memory ({project['identity_kind']}:{project['identity_value']})",
        f"Budget: {compact['used_chars']}/{budget} chars",
    ]
    for type_name in sorted(TYPE_ORDER, key=TYPE_ORDER.__getitem__):
        group = [entry for entry in entries if entry["type"] == type_name]
        if not group:
            continue
        lines.append("")
        lines.append(f"Active {type_name.title()}s:")
        for entry in group:
            lines.append(compact_entry_text(entry))
    if compact["omitted_count"]:
        lines.append("")
        lines.append(
            f"{compact['omitted_count']} active memory entries were omitted due to startup budget. "
            "Run /get-learnings for the full active set."
        )
    return "\n".join(lines)


def format_apply_text(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No memory changes applied."
    lines = ["Applied memory changes:"]
    for result in results:
        action = result["action"]
        if action == "create":
            lines.append(f"- Created #{result['id']}")
        elif action == "update":
            lines.append(f"- Updated #{result['target_id']}")
        elif action == "archive":
            lines.append(f"- Archived #{result['target_id']}")
    return "\n".join(lines)
