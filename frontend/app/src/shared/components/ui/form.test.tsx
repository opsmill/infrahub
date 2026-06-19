import { describe, expect, it } from "vitest";

import { findErrorMessage } from "@/shared/components/ui/form";

describe("findErrorMessage", () => {
  it("returns undefined when there is no error", () => {
    expect(findErrorMessage(undefined)).toBeUndefined();
    expect(findErrorMessage(null)).toBeUndefined();
  });

  it("returns a field's own error message", () => {
    expect(findErrorMessage({ type: "required", message: "Required", ref: {} })).toBe("Required");
  });

  it("descends into a nested child-field error", () => {
    // RHF nests child-field errors under the parent path, e.g. a from-pool
    // allocation's prefix-length field.
    const error = {
      value: {
        from_pool: { prefixlen: { type: "validate", message: "Value must be at most 128" } },
      },
    };
    expect(findErrorMessage(error)).toBe("Value must be at most 128");
  });

  it("ignores the type/ref keys and an empty message", () => {
    expect(findErrorMessage({ type: "validate", ref: {}, message: "" })).toBeUndefined();
  });

  it("returns undefined when no message exists anywhere in the tree", () => {
    expect(findErrorMessage({ value: { from_pool: { id: { ref: {} } } } })).toBeUndefined();
  });
});
