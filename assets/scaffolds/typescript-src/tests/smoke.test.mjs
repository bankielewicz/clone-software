import assert from "node:assert/strict";
import test from "node:test";

import { statusMessage } from "../src/index.ts";

test("statusMessage returns the exact neutral readiness message", () => {
  assert.equal(statusMessage("Example"), "Example is ready.");
});

test("statusMessage rejects an empty product name", () => {
  assert.throws(() => statusMessage("  "), {
    name: "TypeError",
    message: "productName must not be empty",
  });
});
