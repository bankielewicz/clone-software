from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.clonepack.constants import PLAYBOOKS, RECORD_KINDS
from scripts.clonepack.pack import _record_kind_for_id


SKILL_ROOT = Path(__file__).resolve().parents[1]
FORMAL_ID = re.compile(
    r"\b(?:REQ-GAP-\d{3,}-\d{2,}|AC-GAP-\d{3,}-\d{2,}|"
    r"TEST-GAP-\d{3,}-\d{2,}|STEP-GAP-\d{3,}-\d{2,}|CHANGE-GAP-\d{3,}-\d{2,}|"
    r"[A-Z]+(?:-[A-Z]+)*-\d{3,})\b"
)
NON_RECORD_TOKENS = {"ISO-8601", "SHA-256"}


class TraceVocabularyTests(unittest.TestCase):
    def test_every_template_identifier_participates_in_the_runtime_vocabulary(self) -> None:
        unresolved: dict[str, list[str]] = {}
        for directory in (SKILL_ROOT / "assets" / "templates", SKILL_ROOT / "assets" / "templates-v2"):
            for path in sorted(directory.glob("*")):
                if not path.is_file():
                    continue
                identifiers = sorted(set(FORMAL_ID.findall(path.read_text(encoding="utf-8"))))
                missing = [
                    identifier
                    for identifier in identifiers
                    if identifier not in NON_RECORD_TOKENS and _record_kind_for_id(identifier) is None
                ]
                if missing:
                    unresolved[path.relative_to(SKILL_ROOT).as_posix()] = missing
        self.assertEqual(unresolved, {})

    def test_clone_index_schema_and_runtime_expose_the_same_record_kinds(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "assets" / "schemas" / "clone-index-v2.schema.json").read_text(encoding="utf-8")
        )
        schema_kinds = set(schema["$defs"]["record"]["properties"]["kind"]["enum"])
        self.assertEqual(schema_kinds, RECORD_KINDS)

    def test_every_controlled_playbook_has_a_reference_contract(self) -> None:
        self.assertEqual(
            {path.stem for path in (SKILL_ROOT / "references").glob("*.md") if path.stem in PLAYBOOKS},
            PLAYBOOKS,
        )


if __name__ == "__main__":
    unittest.main()
