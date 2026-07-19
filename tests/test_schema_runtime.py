from __future__ import annotations

import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT))
from scripts.clonepack.schema import validate_instance


class SchemaRuntimeTests(unittest.TestCase):
    def locations(self, instance: object, schema: dict[str, object]) -> list[str]:
        return [violation.pointer for violation in validate_instance(instance, schema)]

    def test_local_ref_object_and_boolean_integer_distinction(self) -> None:
        schema = {
            "type": "object",
            "required": ["count", "missing"],
            "properties": {"count": {"$ref": "#/$defs/integer"}},
            "patternProperties": {"^FLAG_": {"type": "boolean"}},
            "additionalProperties": False,
            "$defs": {"integer": {"type": "integer"}},
        }

        self.assertEqual(
            self.locations({"count": True, "FLAG_READY": 1, "extra": None}, schema),
            ["/FLAG_READY", "/count", "/extra", "/missing"],
        )

    def test_array_items_minimum_uniqueness_and_string_contracts(self) -> None:
        schema = {
            "type": "array",
            "minItems": 3,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 3, "pattern": "^[A-Z]+$"},
        }

        self.assertEqual(
            self.locations(["aa", "aa"], schema),
            ["", "/0", "/0", "/1", "/1", "/1"],
        )

    def test_const_enum_one_of_bounds_and_datetime(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "constant": {"const": True},
                "choice": {"enum": [1]},
                "one": {"oneOf": [{"type": "number"}, {"type": "integer"}]},
                "minimum": {"type": "number", "minimum": 1},
                "exclusive": {"type": "number", "exclusiveMinimum": 0},
                "maximum": {"type": "number", "maximum": 10},
                "timestamp": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": False,
        }
        instance = {
            "constant": 1,
            "choice": True,
            "one": 1,
            "minimum": 0,
            "exclusive": 0,
            "maximum": 11,
            "timestamp": "2026-07-18 12:00:00",
        }

        self.assertEqual(
            self.locations(instance, schema),
            ["/choice", "/constant", "/exclusive", "/maximum", "/minimum", "/one", "/timestamp"],
        )

    def test_min_properties_is_enforced(self) -> None:
        self.assertEqual(
            self.locations({}, {"type": "object", "minProperties": 1}),
            [""],
        )

    def test_all_of_any_of_not_and_conditionals(self) -> None:
        conditional = {
            "type": "object",
            "properties": {"mode": {"enum": ["strict", "relaxed"]}, "payload": {"type": "string"}},
            "required": ["mode"],
            "allOf": [
                {
                    "if": {"properties": {"mode": {"const": "strict"}}},
                    "then": {"required": ["payload"], "properties": {"payload": {"minLength": 3}}},
                    "else": {"not": {"required": ["payload"]}},
                }
            ],
        }

        self.assertEqual(self.locations({"mode": "strict"}, conditional), ["/payload"])
        self.assertEqual(self.locations({"mode": "relaxed", "payload": "set"}, conditional), [""])
        self.assertEqual(self.locations(2, {"anyOf": [{"const": 1}, {"const": 2}]}), [])
        self.assertEqual(self.locations(3, {"anyOf": [{"const": 1}, {"const": 2}]}), [""])
        self.assertEqual(self.locations(4, {"allOf": [{"minimum": 1}, {"maximum": 3}]}), [""])


if __name__ == "__main__":
    unittest.main()
