from __future__ import annotations

from research.models import Finding, ResearchSession


def save_finding(
    session_id: int,
    file_path: str,
    note: str,
    line_start: int | None = None,
    line_end: int | None = None,
) -> str:
    session = ResearchSession.objects.get(id=session_id)
    finding = Finding.objects.create(
        session=session,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        note=note,
    )
    return f"Saved finding {finding.id} for session {session_id}."


def get_previous_findings(repo_url: str) -> list[dict[str, str]]:
    findings = (
        Finding.objects.select_related("session", "session__repository")
        .filter(session__repository__url=repo_url)
        .order_by("-created_at")[:20]
    )
    return [
        {
            "session_question": finding.session.question,
            "file_path": finding.file_path,
            "note": finding.note,
        }
        for finding in findings
    ]
