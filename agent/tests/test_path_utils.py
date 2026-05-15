from pathlib import Path
from unittest import TestCase

from agent.path_utils import normalize_repo_relative_path


class PathUtilsTests(TestCase):
    def test_repo_cache_path_becomes_dot(self) -> None:
        repo_root = str(Path("repo_cache/pallets_click").resolve())
        result = normalize_repo_relative_path("repo_cache/pallets_click", repo_root)
        self.assertEqual(result, ".")

    def test_repo_cache_windows_path_becomes_dot(self) -> None:
        repo_root = str(Path("repo_cache/pallets_click").resolve())
        result = normalize_repo_relative_path(r"repo_cache\pallets_click", repo_root)
        self.assertEqual(result, ".")

    def test_relative_path_unchanged(self) -> None:
        repo_root = str(Path("repo_cache/pallets_click").resolve())
        result = normalize_repo_relative_path("src/click/core.py", repo_root)
        self.assertEqual(result, "src/click/core.py")
