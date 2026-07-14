import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mdx2apple


class Mdx2AppleTests(unittest.TestCase):
    def test_clean_entry_keeps_list_items_balanced(self):
        entry = """<d:entry id="word">
<d:index d:value="word"/>
<h1 class="headword">word</h1>
<li class="sense"><span class="def">a definition</span></li>
</d:entry>"""

        cleaned = mdx2apple.clean_entry(entry)

        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.count("<li>"), cleaned.count("</li>"))

    @patch("mdx2apple.subprocess.run")
    def test_convert_mdx_uses_pyglossary_python_entrypoint(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")

        with tempfile.TemporaryDirectory() as directory:
            output = mdx2apple.convert_mdx(Path("example.mdx"), Path(directory))

        command = run.call_args.args[0]
        self.assertEqual(command[:3], [
            sys.executable,
            "-c",
            "from pyglossary.ui.main import main; main()",
        ])
        self.assertEqual(command[-2:], ["--write-format=AppleDict", "-v3"])
        self.assertEqual(output.name, "temp.apple")

    @patch("mdx2apple.subprocess.run")
    def test_run_make_passes_ddk_path_as_override(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        ddk_path = Path("/tmp/Dictionary Development Kit")

        mdx2apple.run_make(ddk_path, "install")

        run.assert_called_once_with(
            ["make", f"DICT_BUILD_TOOL_DIR={ddk_path}", "install"],
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
