from __future__ import annotations

import re

from research.models import Finding, ResearchSession


# Matches: `src/click/core.py` line 1347  or  src/click/core.py:1347
CITATION_PATTERN = re.compile(
    r"`([^`\n]+\.[a-zA-Z0-9]+)`(?:\s+(?:at\s+)?line\s+(\d+))?"
    r"|([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+):(\d+)",
    re.IGNORECASE,
)


def persist_citations_from_answer(session: ResearchSession, final_answer: str) -> int:
    """Create Finding rows from inline citations when the model skipped save_finding."""
    if session.findings.exists():
        return 0

    created = 0
    seen: set[tuple[str, int | None]] = set()

    for match in CITATION_PATTERN.finditer(final_answer):
        file_path = match.group(1) or match.group(3)
        line_raw = match.group(2) or match.group(4)
        if not file_path or "://" in file_path:
            continue

        file_path = file_path.strip().lstrip("./")
        line_start = int(line_raw) if line_raw else None
        key = (file_path, line_start)
        if key in seen:
            continue
        seen.add(key)

        Finding.objects.create(
            session=session,
            file_path=file_path,
            line_start=line_start,
            line_end=line_start,
            note="Auto-saved from final answer citation.",
        )
        created += 1

    return created
