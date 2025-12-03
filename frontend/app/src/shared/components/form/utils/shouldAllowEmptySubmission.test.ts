import { describe, expect, it } from "vitest";

import type { ModelSchema } from "@/entities/schema/types";

import { generateAttributeSchema } from "../../../../../tests/fake/schema";
import { shouldAllowEmptySubmission } from "./shouldAllowEmptySubmission";

describe("shouldAllowEmptySubmission", () => {
  it("returns true when all attributes are read-only", () => {
    // GIVEN: A schema where all attributes are read-only (like NumberPool or computed fields)
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "number_pool_attr", read_only: true }),
        generateAttributeSchema({ name: "computed_attr", read_only: true }),
      ],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("returns false when some attributes are not read-only", () => {
    // GIVEN: A schema with some editable attributes
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "editable_attr", read_only: false }),
        generateAttributeSchema({ name: "read_only_attr", read_only: true }),
      ],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("returns false when all attributes are editable", () => {
    // GIVEN: A schema where all attributes are editable
    const schema = {
      attributes: [
        generateAttributeSchema({ name: "attr1", read_only: false }),
        generateAttributeSchema({ name: "attr2", read_only: false }),
      ],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(false);
  });

  it("returns true when schema has no attributes", () => {
    // GIVEN: A schema with no attributes (only relationships)
    const schema = {
      attributes: [],
    } as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(true);
  });

  it("returns true when attributes is undefined", () => {
    // GIVEN: A schema where attributes is undefined
    const schema = {} as ModelSchema;

    // WHEN
    const result = shouldAllowEmptySubmission(schema);

    // THEN
    expect(result).toBe(true);
  });
});
