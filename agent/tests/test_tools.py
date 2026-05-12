from pathlib import Path
from unittest import TestCase

from agent.tools.code_tools import (
    get_file_outline,
    list_files,
    read_file,
    search_code,
)


class CodeToolsTests(TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1] / "tools"

    def test_list_files_skips_ignored_directories(self) -> None:
        files = list_files(str(self.repo_root))

        self.assertIn("code_tools.py", files)
        self.assertNotIn("__pycache__", "\n".join(files))

    def test_read_file_returns_numbered_line_range(self) -> None:
        output = read_file(str(self.repo_root), "code_tools.py", start_line=1, end_line=20)

        self.assertIn("1: from __future__ import annotations", output)
        self.assertLessEqual(len(output.splitlines()), 20)

    def test_search_and_outline_find_code_tool_function(self) -> None:
        matches = search_code(str(self.repo_root), "def list_files", file_pattern="*.py")
        outline = get_file_outline(str(self.repo_root), "code_tools.py")

        self.assertTrue(any(match["file"] == "code_tools.py" for match in matches))
        self.assertTrue(
            any(item["kind"] == "def" and item["name"] == "list_files" for item in outline)
        )
