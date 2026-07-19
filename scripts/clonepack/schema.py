from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any


class SchemaDefinitionError(Exception):
    """The packaged schema cannot be loaded or contains an unsupported reference."""


@dataclass(order=True, frozen=True)
class SchemaViolation:
    pointer: str
    message: str


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _child(pointer: str, value: str | int) -> str:
    return f"{pointer}/{_escape_pointer(str(value))}"


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return not any(isinstance(value, bool) for value in (left, right)) and left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return set(left) == set(right) and all(_json_equal(left[key], right[key]) for key in left)
    return left == right


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "null":
        return instance is None
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "number":
        return (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and (not isinstance(instance, float) or math.isfinite(instance))
        )
    if expected == "integer":
        return (
            isinstance(instance, int)
            and not isinstance(instance, bool)
        ) or (
            isinstance(instance, float)
            and math.isfinite(instance)
            and instance.is_integer()
        )
    raise SchemaDefinitionError(f"unsupported schema type: {expected!r}")


def _resolve_reference(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if reference == "#":
        return root_schema
    if not reference.startswith("#/"):
        raise SchemaDefinitionError(f"only local JSON Pointer references are supported: {reference!r}")
    current: Any = root_schema
    for raw in reference[2:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            raise SchemaDefinitionError(f"schema reference does not resolve: {reference!r}")
        current = current[token]
    if not isinstance(current, dict):
        raise SchemaDefinitionError(f"schema reference does not name an object: {reference!r}")
    return current


def _valid_datetime(value: str) -> bool:
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})",
        value,
    ):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("z", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _walk(
    instance: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    pointer: str,
) -> list[SchemaViolation]:
    violations: list[SchemaViolation] = []

    reference = schema.get("$ref")
    if reference is not None:
        if not isinstance(reference, str):
            raise SchemaDefinitionError("$ref must be a string")
        violations.extend(_walk(instance, _resolve_reference(root_schema, reference), root_schema, pointer))

    if "allOf" in schema:
        branches = schema["allOf"]
        if not isinstance(branches, list) or not branches or any(not isinstance(item, dict) for item in branches):
            raise SchemaDefinitionError("allOf must be a non-empty array of schemas")
        for branch in branches:
            violations.extend(_walk(instance, branch, root_schema, pointer))

    if "anyOf" in schema:
        branches = schema["anyOf"]
        if not isinstance(branches, list) or not branches or any(not isinstance(item, dict) for item in branches):
            raise SchemaDefinitionError("anyOf must be a non-empty array of schemas")
        matches = sum(not _walk(instance, branch, root_schema, pointer) for branch in branches)
        if matches == 0:
            violations.append(SchemaViolation(pointer, "anyOf must match at least one subschema"))

    if "oneOf" in schema:
        branches = schema["oneOf"]
        if not isinstance(branches, list) or not branches or any(not isinstance(item, dict) for item in branches):
            raise SchemaDefinitionError("oneOf must be a non-empty array of schemas")
        matches = sum(not _walk(instance, branch, root_schema, pointer) for branch in branches)
        if matches != 1:
            violations.append(SchemaViolation(pointer, f"oneOf must match exactly one subschema; matched {matches}"))

    if "not" in schema:
        branch = schema["not"]
        if not isinstance(branch, dict):
            raise SchemaDefinitionError("not must be a schema object")
        if not _walk(instance, branch, root_schema, pointer):
            violations.append(SchemaViolation(pointer, "not subschema must not match"))

    if "if" in schema:
        condition = schema["if"]
        if not isinstance(condition, dict):
            raise SchemaDefinitionError("if must be a schema object")
        condition_matches = not _walk(instance, condition, root_schema, pointer)
        selected_keyword = "then" if condition_matches else "else"
        if selected_keyword in schema:
            selected = schema[selected_keyword]
            if not isinstance(selected, dict):
                raise SchemaDefinitionError(f"{selected_keyword} must be a schema object")
            violations.extend(_walk(instance, selected, root_schema, pointer))

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not expected_types or any(not isinstance(item, str) for item in expected_types):
            raise SchemaDefinitionError("type must be a string or non-empty string array")
        if not any(_type_matches(instance, item) for item in expected_types):
            rendered = ", ".join(expected_types)
            violations.append(SchemaViolation(pointer, f"expected type {rendered}"))
            return violations

    if "const" in schema and not _json_equal(instance, schema["const"]):
        violations.append(SchemaViolation(pointer, f"value must equal const {schema['const']!r}"))

    if "enum" in schema:
        choices = schema["enum"]
        if not isinstance(choices, list):
            raise SchemaDefinitionError("enum must be an array")
        if not any(_json_equal(instance, choice) for choice in choices):
            violations.append(SchemaViolation(pointer, "value is not in the allowed enum"))

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise SchemaDefinitionError("required must be a string array")
        for key in sorted(set(required) - set(instance)):
            violations.append(SchemaViolation(_child(pointer, key), "required property is missing"))

        properties = schema.get("properties", {})
        patterns = schema.get("patternProperties", {})
        if not isinstance(properties, dict) or not isinstance(patterns, dict):
            raise SchemaDefinitionError("properties and patternProperties must be objects")
        compiled_patterns: list[tuple[str, re.Pattern[str], dict[str, Any]]] = []
        for expression, subschema in sorted(patterns.items()):
            if not isinstance(expression, str) or not isinstance(subschema, dict):
                raise SchemaDefinitionError("patternProperties entries must map strings to schemas")
            try:
                compiled_patterns.append((expression, re.compile(expression), subschema))
            except re.error as exc:
                raise SchemaDefinitionError(f"invalid patternProperties expression {expression!r}: {exc}") from exc

        for key in sorted(instance):
            value = instance[key]
            matched = False
            if key in properties:
                subschema = properties[key]
                if not isinstance(subschema, dict):
                    raise SchemaDefinitionError(f"property schema must be an object: {key!r}")
                violations.extend(_walk(value, subschema, root_schema, _child(pointer, key)))
                matched = True
            for _, expression, subschema in compiled_patterns:
                if expression.search(key):
                    violations.extend(_walk(value, subschema, root_schema, _child(pointer, key)))
                    matched = True
            if not matched:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    violations.append(SchemaViolation(_child(pointer, key), "additional property is not allowed"))
                elif isinstance(additional, dict):
                    violations.extend(_walk(value, additional, root_schema, _child(pointer, key)))
                elif additional is not True:
                    raise SchemaDefinitionError("additionalProperties must be a boolean or schema")

        minimum_properties = schema.get("minProperties")
        if minimum_properties is not None and len(instance) < minimum_properties:
            violations.append(SchemaViolation(pointer, f"object requires at least {minimum_properties} properties"))

    if isinstance(instance, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(instance) < minimum_items:
            violations.append(SchemaViolation(pointer, f"array requires at least {minimum_items} items"))
        if schema.get("uniqueItems") is True:
            for right in range(len(instance)):
                if any(_json_equal(instance[left], instance[right]) for left in range(right)):
                    violations.append(SchemaViolation(_child(pointer, right), "array item is not unique"))
        items = schema.get("items")
        if items is not None:
            if not isinstance(items, dict):
                raise SchemaDefinitionError("items must be a schema object")
            for index, item in enumerate(instance):
                violations.extend(_walk(item, items, root_schema, _child(pointer, index)))

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(instance) < minimum_length:
            violations.append(SchemaViolation(pointer, f"string requires at least {minimum_length} characters"))
        pattern = schema.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                raise SchemaDefinitionError("pattern must be a string")
            try:
                matched = re.search(pattern, instance)
            except re.error as exc:
                raise SchemaDefinitionError(f"invalid schema pattern {pattern!r}: {exc}") from exc
            if matched is None:
                violations.append(SchemaViolation(pointer, f"string does not match pattern {pattern!r}"))
        if schema.get("format") == "date-time" and not _valid_datetime(instance):
            violations.append(SchemaViolation(pointer, "string is not an RFC 3339 date-time"))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        for keyword, comparator, phrase in (
            ("minimum", lambda value, bound: value < bound, "at least"),
            ("exclusiveMinimum", lambda value, bound: value <= bound, "greater than"),
            ("maximum", lambda value, bound: value > bound, "at most"),
            ("exclusiveMaximum", lambda value, bound: value >= bound, "less than"),
        ):
            if keyword in schema and comparator(instance, schema[keyword]):
                violations.append(SchemaViolation(pointer, f"number must be {phrase} {schema[keyword]}"))

    return violations


def validate_instance(instance: Any, schema: dict[str, Any]) -> list[SchemaViolation]:
    """Validate one JSON-compatible value against the supported Draft 2020-12 subset."""

    if not isinstance(schema, dict):
        raise SchemaDefinitionError("schema root must be an object")
    return sorted(set(_walk(instance, schema, schema, "")))


@lru_cache(maxsize=None)
def load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SchemaDefinitionError(f"cannot load schema {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SchemaDefinitionError(f"schema root must be an object: {path}")
    return value


def validate_schema_file(instance: Any, path: Path) -> list[SchemaViolation]:
    return validate_instance(instance, load_schema(path.resolve()))
