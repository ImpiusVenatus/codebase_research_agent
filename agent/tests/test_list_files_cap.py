from pathlib import Path
from unittest import TestCase

from agent.tools.code_tools import MAX_LIST_FILES, list_files


class ListFilesCapTests(TestCase):
    def test_list_files_caps_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        files = list_files(str(repo_root), path=".", max_depth=2)
        capped = [path for path in files if path.startswith("... and")]
        self.assertTrue(len(files) <= MAX_LIST_FILES + 1 or capped)
