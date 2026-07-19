from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clone_app.__main__ import main  # noqa: E402


class CommandSmokeTest(unittest.TestCase):
    def test_main_emits_machine_readable_status(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--name", "Example"])

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue()), {"name": "Example", "status": "ready"})


if __name__ == "__main__":
    unittest.main()
