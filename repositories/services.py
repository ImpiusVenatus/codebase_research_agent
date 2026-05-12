from pathlib import Path
from urllib.parse import urlparse
import re

from django.conf import settings
from django.utils import timezone
from git import Repo

from .models import Repository


class RepositoryService:
    @classmethod
    def get_or_clone(cls, repo_url: str) -> Repository:
        name = cls.sanitize_repo_name(repo_url)
        repository, _ = Repository.objects.get_or_create(
            url=repo_url,
            defaults={"name": name},
        )

        if repository.local_clone_path and Path(repository.local_clone_path).exists():
            return repository

        cache_dir = Path(settings.REPO_CACHE_DIR)
        clone_path = cache_dir / name
        cache_dir.mkdir(parents=True, exist_ok=True)

        if not clone_path.exists():
            Repo.clone_from(repo_url, clone_path, depth=1)

        repository.name = name
        repository.local_clone_path = str(clone_path)
        repository.last_indexed_at = timezone.now()
        repository.save(
            update_fields=["name", "local_clone_path", "last_indexed_at"],
        )
        return repository

    @staticmethod
    def sanitize_repo_name(repo_url: str) -> str:
        parsed = urlparse(repo_url)

        if parsed.scheme and parsed.netloc:
            raw_name = parsed.path
        else:
            raw_name = repo_url

        raw_name = raw_name.removesuffix(".git").strip("/")
        sanitized = re.sub(r"[^A-Za-z0-9]+", "_", raw_name).strip("_").lower()
        return sanitized or "repository"
