import { describe, expect, it } from "vitest";

import getFormStructureForFilters from "../../../src/utils/formStructureForFilters";
import { formFields, schema } from "../../mocks/data/filters";

describe("Form structure for filters", () => {
  it("should return a correct form structure", () => {
    const calculatedAttributes = getFormStructureForFilters(schema, [], {});

    expect(JSON.stringify(calculatedAttributes)).toStrictEqual(JSON.stringify(formFields));
  });
});
