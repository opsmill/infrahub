import { describe, expect, it } from "vitest";

import {
  type FilterDefinition,
  getFilterDefinitionLabel,
  getFilterDefinitionName,
} from "@/entities/nodes/object/domain/filter-definition";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

describe("getFilterDefinitionName", () => {
  it("returns schema name for attribute definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "attribute",
      schema: generateAttributeSchema({ name: "hostname" }),
    };

    // WHEN
    const result = getFilterDefinitionName(def);

    // THEN
    expect(result).toBe("hostname");
  });

  it("returns schema name for relationship definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "relationship",
      schema: generateRelationshipSchema({ name: "site" }),
    };

    // WHEN
    const result = getFilterDefinitionName(def);

    // THEN
    expect(result).toBe("site");
  });

  it("returns name for metadata-date definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "metadata-date",
      name: "node_metadata__created_at",
      label: "Created at",
    };

    // WHEN
    const result = getFilterDefinitionName(def);

    // THEN
    expect(result).toBe("node_metadata__created_at");
  });

  it("returns name for metadata-user definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "metadata-user",
      name: "node_metadata__created_by",
      label: "Created by",
      peer: "CoreAccount",
    };

    // WHEN
    const result = getFilterDefinitionName(def);

    // THEN
    expect(result).toBe("node_metadata__created_by");
  });
});

describe("getFilterDefinitionLabel", () => {
  it("returns schema label for attribute definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "attribute",
      schema: generateAttributeSchema({ name: "hostname", label: "Hostname" }),
    };

    // WHEN
    const result = getFilterDefinitionLabel(def);

    // THEN
    expect(result).toBe("Hostname");
  });

  it("falls back to schema name when label is null", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "attribute",
      schema: generateAttributeSchema({ name: "hostname", label: null }),
    };

    // WHEN
    const result = getFilterDefinitionLabel(def);

    // THEN
    expect(result).toBe("hostname");
  });

  it("returns label for metadata-date definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "metadata-date",
      name: "node_metadata__created_at",
      label: "Created at",
    };

    // WHEN
    const result = getFilterDefinitionLabel(def);

    // THEN
    expect(result).toBe("Created at");
  });

  it("returns label for metadata-user definition", () => {
    // GIVEN
    const def: FilterDefinition = {
      type: "metadata-user",
      name: "node_metadata__created_by",
      label: "Created by",
      peer: "CoreAccount",
    };

    // WHEN
    const result = getFilterDefinitionLabel(def);

    // THEN
    expect(result).toBe("Created by");
  });
});
