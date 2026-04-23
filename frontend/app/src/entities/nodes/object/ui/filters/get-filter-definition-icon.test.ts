import { describe, expect, it } from "vitest";

import type { FilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { getFilterDefinitionIcon } from "@/entities/nodes/object/ui/filters/get-filter-definition-icon";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../../tests/fake/schema";

describe("getFilterDefinitionIcon", () => {
  it("returns calendar-clock icon for datetime attribute", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "attribute",
      schema: generateAttributeSchema({ kind: "DateTime" }),
    };

    // WHEN
    const result = getFilterDefinitionIcon(def);

    // THEN
    expect(result).toBe("mdi:calendar-clock");
  });

  it("returns text icon for text attribute", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "attribute",
      schema: generateAttributeSchema({ kind: "Text" }),
    };

    // WHEN
    const result = getFilterDefinitionIcon(def);

    // THEN
    expect(result).toBe("mdi:text");
  });

  it("returns default icon for relationship definition", () => {
    // GIVEN
    const def: FilterDefinition = { type: "relationship", schema: generateRelationshipSchema() };

    // WHEN
    const result = getFilterDefinitionIcon(def);

    // THEN
    expect(result).toBe("mdi:cube-outline");
  });

  it("returns calendar-clock icon for metadata-date definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "metadata-date",
      name: "node_metadata__created_at",
      label: "Created at",
    };

    // WHEN
    const result = getFilterDefinitionIcon(def);

    // THEN
    expect(result).toBe("mdi:calendar-clock");
  });

  it("returns account icon for metadata-user definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "metadata-user",
      name: "node_metadata__created_by",
      label: "Created by",
      peer: "CoreAccount",
    };

    // WHEN
    const result = getFilterDefinitionIcon(def);

    // THEN
    expect(result).toBe("mdi:account");
  });
});
