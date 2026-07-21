import re
from typing import Any


def _tail(lines: list[str], max_lines: int) -> str:
    """Join lines, keeping only the last max_lines entries.

    Errors cluster at the end of a section, so the tail is the part
    worth sending to the LLM.

    Args:
        lines: Log lines for one section.
        max_lines: Maximum number of lines to keep.

    Returns:
        Joined and stripped text of at most max_lines lines.
    """
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines).strip()


def parse_log_sections(
    raw_log: str,
    max_lines: int | None = None,
) -> dict[str, str]:
    """Parse error sections from raw GitHub Actions logs.

    Attempts to extract structured sections using GitHub log markers
    (##[group], ##[endgroup], ##[error]). Falls back to last N lines
    if markers not found. Every section is capped at max_lines
    (keeping the tail) so the LLM prompt stays bounded.

    Args:
        raw_log: Raw job log text from GitHub API.
        max_lines: Maximum lines kept per section (default 1000).

    Returns:
        Dictionary with keys:
        - step_context: Step that was running (from ##[group])
        - actual_error: Error output between step and ##[error]
        - github_error: Runner status from ##[error] onward
    """
    if max_lines is None or max_lines <= 0:
        max_lines = 1000
    cleaned = re.sub(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s",
        "",
        raw_log,
        flags=re.MULTILINE,
    )
    lines = cleaned.split("\n")

    error_idx = -1
    for i, line in enumerate(lines):
        if "##[error]" in line:
            error_idx = i
            break

    if error_idx == -1:
        return {
            "step_context": "No formal group block detected.",
            "actual_error": (
                "No explicit ##[error] tag found. Providing the last "
                f"{max_lines} lines of execution."
            ),
            "github_error": _tail(lines, max_lines),
        }

    endgroup_idx = 0
    for i in range(error_idx, -1, -1):
        if "##[endgroup]" in lines[i]:
            endgroup_idx = i
            break

    group_idx = 0
    for i in range(endgroup_idx, -1, -1):
        if "##[group]" in lines[i]:
            group_idx = i
            break

    cleanup_idx = len(lines)
    for i in range(error_idx, len(lines)):
        if "Post job cleanup" in lines[i]:
            cleanup_idx = i
            break

    return {
        "step_context": _tail(lines[group_idx : endgroup_idx + 1], max_lines),
        "actual_error": _tail(lines[endgroup_idx + 1 : error_idx], max_lines),
        "github_error": _tail(lines[error_idx:cleanup_idx], max_lines),
    }