import { describe, expect, it } from "vitest";

import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";

import type { ConvertFormFieldValue } from "@/entities/nodes/convert/types";

import { getFieldsMappingPayload } from "./get-fields-mapping-payload";

describe("getFieldsMappingPayload", () => {
  it("should handle empty field list", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [];
    const formData = {};

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({});
  });

  it("should skip fields that have no corresponding form data", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "field1",
        type: "text",
      } as unknown as DynamicFieldProps,
      {
        name: "field2",
        type: "relationship",
        relationship: {
          cardinality: "one",
        },
        peer: "peerKind",
      } as unknown as DynamicFieldProps,
    ];
    const formData = {};

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      field1: { use_default_value: true },
      field2: { use_default_value: true },
    });
  });

  it("should preserve field mapping from source object", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "field1",
        type: "text",
      } as unknown as DynamicFieldProps,
    ];
    const formData: Record<string, ConvertFormFieldValue> = {
      field1: {
        source: { type: "source", name: "source_field_name" },
        value: "test value",
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      field1: {
        source_field: "source_field_name",
      },
    });
  });

  it("should handle multiple related entities", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "tags",
        type: "relationship",
        relationship: { cardinality: "many" },
      } as DynamicFieldProps,
    ];
    const formData: Record<string, FormFieldValue> = {
      tags: {
        source: { type: "user" },
        value: ["id1", "id2", "id3"],
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      tags: {
        data: { peer_ids: ["id1", "id2", "id3"] },
      },
    });
  });

  it("should handle single related entity", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "field1",
        type: "relationship",
        relationship: { cardinality: "one" },
      } as DynamicFieldProps,
    ];
    const formData: Record<string, FormFieldValue> = {
      field1: {
        source: { type: "user" },
        value: "peer_id1",
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      field1: {
        data: { peer_id: "peer_id1" },
      },
    });
  });

  it("should store user-provided attribute value", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "description",
        type: "text",
      } as unknown as DynamicFieldProps,
    ];
    const formData: Record<string, FormFieldValue> = {
      description: {
        source: { type: "user" },
        value: "Test description",
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      description: {
        data: { attribute_value: "Test description" },
      },
    });
  });

  it("should fall back to default value when no data provided", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "status",
        type: "text",
      } as unknown as DynamicFieldProps,
    ];
    const formData: Record<string, FormFieldValue> = {
      status: {
        source: { type: "user" },
        value: null,
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      status: {
        data: { attribute_value: null },
      },
    });
  });

  it("should process mixed field types correctly", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "name",
        type: "text",
      } as unknown as DynamicFieldProps,
      {
        name: "tags",
        type: "relationship",
        relationship: { cardinality: "many" },
      } as DynamicFieldProps,
      {
        name: "owner",
        type: "relationship",
        relationship: { cardinality: "one" },
      } as DynamicFieldProps,
      {
        name: "description",
        type: "text",
      } as unknown as DynamicFieldProps,
    ];
    const formData: Record<string, ConvertFormFieldValue | FormFieldValue> = {
      name: {
        source: { type: "source", name: "original_name" },
        value: null,
      },
      tags: {
        source: { type: "user" },
        value: ["tag1", "tag2"],
      },
      owner: {
        source: { type: "user" },
        value: "owner123",
      },
      description: {
        source: null,
        value: null,
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      name: {
        source_field: "original_name",
      },
      tags: {
        data: { peer_ids: ["tag1", "tag2"] },
      },
      owner: {
        data: { peer_id: "owner123" },
      },
      description: {
        use_default_value: true,
      },
    });
  });

  it("should support various attribute value types", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "count",
        type: "number",
      } as unknown as DynamicFieldProps,
      {
        name: "active",
        type: "checkbox",
      } as unknown as DynamicFieldProps,
      {
        name: "items",
        type: "list",
      } as unknown as DynamicFieldProps,
    ];
    const formData: Record<string, ConvertFormFieldValue | FormFieldValue> = {
      count: {
        source: { type: "user" },
        value: 42,
      },
      active: {
        source: { type: "user" },
        value: true,
      },
      items: {
        source: { type: "user" },
        value: ["item1", "item2"],
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      count: {
        data: { attribute_value: 42 },
      },
      active: {
        data: { attribute_value: true },
      },
      items: {
        data: { attribute_value: ["item1", "item2"] },
      },
    });
  });

  it("should only include fields with available data", () => {
    // GIVEN
    const fields: DynamicFieldProps[] = [
      {
        name: "field1",
        type: "text",
      } as unknown as DynamicFieldProps,
      {
        name: "field2",
        type: "text",
      } as unknown as DynamicFieldProps,
    ];
    const formData: Record<string, ConvertFormFieldValue | FormFieldValue> = {
      field1: {
        source: { type: "user" },
        value: "value1",
      },
    };

    // WHEN
    const result = getFieldsMappingPayload(fields, formData);

    // THEN
    expect(result).toEqual({
      field1: {
        data: { attribute_value: "value1" },
      },
      field2: {
        use_default_value: true,
      },
    });
  });
});
