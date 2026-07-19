from __future__ import annotations

import unittest

from scripts.clonepack.common import ClonePackError, safe_relative_path


class SafePathTests(unittest.TestCase):
    def test_accepts_only_canonical_posix_relative_paths(self) -> None:
        self.assertEqual(safe_relative_path("evidence/captures/result.json").as_posix(), "evidence/captures/result.json")
        for value in (
            "",
            ".",
            "..",
            "/absolute",
            "C:/drive",
            "a\\b",
            "a//b",
            "a/./b",
            "a/../b",
            "a/",
            "a\x00b",
            "a\nb",
        ):
            with self.subTest(value=value), self.assertRaises(ClonePackError):
                safe_relative_path(value)


if __name__ == "__main__":
    unittest.main()
