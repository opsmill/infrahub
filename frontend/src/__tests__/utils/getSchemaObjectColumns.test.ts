import { C_deviceAttributeColumns, C_deviceObjectColumns, C_deviceRelationshipColumns, C_deviceSchema } from "../../data/deviceSchema";
import { getSchemaAttributeColumns, getSchemaObjectColumns, getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";

describe("Schema object columns for list view", () => {
  it("should return correct attribute columns", () => {
    const calculatedAttributes = getSchemaAttributeColumns(C_deviceSchema);
    expect(calculatedAttributes).toStrictEqual(C_deviceAttributeColumns);
  });

  it("should return correct relationship columns", () => {
    const calculatedRelationships = getSchemaRelationshipColumns(C_deviceSchema);
    expect(calculatedRelationships).toStrictEqual(C_deviceRelationshipColumns);
  });

  it("should return correct object columns", () => {
    const calculatedObjectColumns = getSchemaObjectColumns(C_deviceSchema);
    expect(calculatedObjectColumns).toStrictEqual(C_deviceObjectColumns);
  });
});
