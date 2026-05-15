from pathlib import Path


def normalize_repo_relative_path(path: str, repo_root: str) -> str:
    """Fix model paths that incorrectly reference repo_cache or absolute clone paths."""
    if not path or path == ".":
        return "."

    normalized = path.replace("\\", "/").strip()
    root = Path(repo_root).resolve()
    root_name = root.name

    lower = normalized.lower()
    if lower.startswith("repo_cache/") or "/repo_cache/" in lower:
        if f"/{root_name}/" in normalized:
            suffix = normalized.split(f"/{root_name}/", 1)[1]
            return suffix or "."
        if normalized.endswith(f"/{root_name}") or normalized == root_name:
            return "."
        return "."

    candidate = Path(normalized)
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
            if resolved == root or root in resolved.parents:
                relative = resolved.relative_to(root)
                return relative.as_posix() or "."
        except (OSError, ValueError):
            pass

    return normalized.lstrip("/") or "."
