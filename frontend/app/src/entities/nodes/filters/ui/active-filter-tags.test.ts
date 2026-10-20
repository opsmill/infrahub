import { describe, expect, it } from "vitest";

import type { UseFormatDateResult } from "@/shared/context/date-preferences-context";

import {
  formatAttributeFilterValue,
  getFilterTagDisplay,
} from "@/entities/nodes/filters/ui/active-filter-tags";
import { objectDecisionOptions } from "@/entities/role-manager/domain/model/decision";

import {
  generateAttributeSchema,
  generateRelationshipSchema,
} from "../../../../../tests/fake/schema";

// Stub the preference-aware formatter; these tests assert labels/conditions, not date formatting.
const formatDate: UseFormatDateResult["formatDate"] = (date) => new Date(date).toISOString();

const syncStatusSchema = generateAttributeSchema({
  name: "sync_status",
  label: "Sync status",
  kind: "Dropdown",
  choices: [
    { name: "in-sync", label: "In Sync" },
    { name: "error-import", label: "Import Error" },
  ],
});

describe("formatAttributeFilterValue", () => {
  it("returns string representation for boolean kind", () => {
    // GIVEN
    const schema = generateAttributeSchema({ kind: "Boolean" });
    const value = true;

    // WHEN
    const result = formatAttributeFilterValue({ schema, value, formatDate });

    // THEN
    expect(result).toBe("true");
  });

  it("returns the value as-is for text kind", () => {
    // GIVEN
    const schema = generateAttributeSchema({ kind: "Text" });
    const value = "hello";

    // WHEN
    const result = formatAttributeFilterValue({ schema, value, formatDate });

    // THEN
    expect(result).toBe("hello");
  });

  it("formats the value as a date for datetime kind, even with choice labels requested", () => {
    // GIVEN
    const schema = generateAttributeSchema({ kind: "DateTime" });
    const value = "2024-01-15T10:30:00Z";

    // WHEN
    const result = formatAttributeFilterValue({
      schema,
      value,
      formatDate,
      showChoiceLabels: true,
    });

    // THEN
    expect(result).toBe("2024-01-15T10:30:00.000Z");
  });

  it("returns string representation for boolean kind with choice labels requested", () => {
    // GIVEN
    const schema = generateAttributeSchema({ kind: "Boolean" });

    // WHEN
    const result = formatAttributeFilterValue({
      schema,
      value: false,
      formatDate,
      showChoiceLabels: true,
    });

    // THEN
    expect(result).toBe("false");
  });

  it("keeps the stored dropdown value when choice labels are not requested", () => {
    // GIVEN
    const value = "error-import";

    // WHEN
    const result = formatAttributeFilterValue({ schema: syncStatusSchema, value, formatDate });

    // THEN
    expect(result).toBe("error-import");
  });

  it("returns the choice label of a dropdown value when choice labels are requested", () => {
    // GIVEN
    const value = "error-import";

    // WHEN
    const result = formatAttributeFilterValue({
      schema: syncStatusSchema,
      value,
      formatDate,
      showChoiceLabels: true,
    });

    // THEN
    expect(result).toBe("Import Error");
  });

  it("keeps the stored dropdown value when it matches no choice", () => {
    // GIVEN
    const value = "error-ref-missing";

    // WHEN
    const result = formatAttributeFilterValue({
      schema: syncStatusSchema,
      value,
      formatDate,
      showChoiceLabels: true,
    });

    // THEN
    expect(result).toBe("error-ref-missing");
  });

  it("keeps the stored value of a text attribute with an enum when choice labels are requested", () => {
    // GIVEN
    const schema = generateAttributeSchema({ kind: "Text", enum: ["OPEN", "MERGED"] });

    // WHEN
    const result = formatAttributeFilterValue({
      schema,
      value: "OPEN",
      formatDate,
      showChoiceLabels: true,
    });

    // THEN
    expect(result).toBe("OPEN");
  });
});

describe("getFilterTagDisplay", () => {
  it("returns label and value for attribute value filter", () => {
    // GIVEN
    const filter = { name: "hostname__value", value: "server01" };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "value",
      filterDefinition: {
        type: "attribute",
        schema: generateAttributeSchema({ name: "hostname", label: "Hostname", kind: "Text" }),
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Hostname",
      condition: "contains",
      value: "server01",
    });
  });

  it("keeps the stored dropdown value in the tag when choice labels are not requested", () => {
    // GIVEN
    const filter = { name: "sync_status__value", value: "error-import" };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "value",
      filterDefinition: { type: "attribute", schema: syncStatusSchema },
    });

    // THEN
    expect(result).toEqual({
      label: "Sync status",
      condition: "contains",
      value: "error-import",
    });
  });

  it("shows the dropdown choice label in the tag when choice labels are requested", () => {
    // GIVEN
    const filter = { name: "sync_status__value", value: "error-import" };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "value",
      filterDefinition: { type: "attribute", schema: syncStatusSchema },
      showChoiceLabels: true,
    });

    // THEN
    expect(result).toEqual({
      label: "Sync status",
      condition: "contains",
      value: "Import Error",
    });
  });

  it("returns null for value filter on a relationship definition", () => {
    // GIVEN
    const filter = { name: "site__value", value: "test" };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "value",
      filterDefinition: {
        type: "relationship",
        schema: generateRelationshipSchema({ name: "site" }),
      },
    });

    // THEN
    expect(result).toBeNull();
  });

  it("returns display labels for relationship ids filter", () => {
    // GIVEN
    const filter = {
      name: "site__ids",
      value: [
        { id: "1", display_label: "Site A" },
        { id: "2", display_label: "Site B" },
      ],
    };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "ids",
      filterDefinition: {
        type: "relationship",
        schema: generateRelationshipSchema({ name: "site", label: "Site" }),
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Site",
      condition: "is any of",
      value: "Site A, Site B",
    });
  });

  it("returns display labels for metadata-user ids filter", () => {
    // GIVEN
    const filter = {
      name: "node_metadata__created_by__ids",
      value: [
        { id: "1", display_label: "Admin" },
        { id: "2", display_label: "User" },
      ],
    };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "ids",
      filterDefinition: {
        type: "metadata-user",
        name: "node_metadata__created_by",
        label: "Created by",
        peer: "CoreAccount",
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Created by",
      condition: "is any of",
      value: "Admin, User",
    });
  });

  it("returns null for ids filter on attribute definition", () => {
    // GIVEN
    const filter = { name: "name__ids", value: ["a"] };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "ids",
      filterDefinition: {
        type: "attribute",
        schema: generateAttributeSchema({ name: "name" }),
      },
    });

    // THEN
    expect(result).toBeNull();
  });

  it("returns is empty condition for isnull filter with true value", () => {
    // GIVEN
    const filter = { name: "description__isnull", value: true };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "isnull",
      filterDefinition: {
        type: "attribute",
        schema: generateAttributeSchema({ name: "description", label: "Description" }),
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Description",
      condition: "is empty",
      value: "",
    });
  });

  it("returns is not empty condition for isnull filter with false value", () => {
    // GIVEN
    const filter = { name: "description__isnull", value: false };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "isnull",
      filterDefinition: {
        type: "attribute",
        schema: generateAttributeSchema({ name: "description", label: "Description" }),
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Description",
      condition: "is not empty",
      value: "",
    });
  });

  it("returns null for unknown field key", () => {
    // GIVEN
    const filter = { name: "name__unknown", value: "test" };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "unknown",
      filterDefinition: {
        type: "attribute",
        schema: generateAttributeSchema({ name: "name" }),
      },
    });

    // THEN
    expect(result).toBeNull();
  });

  it("returns the decision label for a decision filter definition", () => {
    // GIVEN
    const filter = { name: "decision__value", value: 2 };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "value",
      filterDefinition: {
        type: "permission-decision",
        schema: generateAttributeSchema({ name: "decision", label: "Decision", kind: "Number" }),
        options: objectDecisionOptions,
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Decision",
      condition: "is",
      value: "Allow on default branch",
    });
  });

  it("falls back to the raw value when the decision value is not in the options", () => {
    // GIVEN
    const filter = { name: "decision__value", value: 99 };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "value",
      filterDefinition: {
        type: "permission-decision",
        schema: generateAttributeSchema({ name: "decision", label: "Decision", kind: "Number" }),
        options: objectDecisionOptions,
      },
    });

    // THEN
    expect(result).toEqual({
      label: "Decision",
      condition: "is",
      value: 99,
    });
  });

  it("returns before/after display for metadata-date filters", () => {
    // GIVEN
    const filter = { name: "node_metadata__created_at__after", value: "2024-01-15T10:30:00.000Z" };

    // WHEN
    const result = getFilterTagDisplay({
      formatDate,
      filter,
      fieldKey: "after",
      filterDefinition: {
        type: "metadata-date",
        name: "node_metadata__created_at",
        label: "Created at",
      },
    });

    // THEN
    expect(result).not.toBeNull();
    expect(result!.label).toBe("Created at");
    expect(result!.condition).toBe("after");
  });
});
