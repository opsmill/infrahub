import { describe, expect, it } from "vitest";
import { updateObjectWithId } from "../../../src/graphql/mutations/objects/updateObjectWithId";
import getMutationMetaDetailsFromFormData from "../../../src/utils/getMutationMetaDetailsFromFormData";
import { stringifyWithoutQuotes } from "../../../src/utils/string";
import {
  deviceDetailsMocksData,
  deviceDetailsMocksSchema,
  mutationStringForMetaEdit,
  newDataForMetaEdit,
  updatedObjectForMetaEdit,
} from "../../mocks/data/devices";

const updatedObject = getMutationMetaDetailsFromFormData(
  deviceDetailsMocksSchema[0],
  newDataForMetaEdit,
  deviceDetailsMocksData.InfraDevice.edges[0].node,
  "relationship",
  "site",
  deviceDetailsMocksData.InfraDevice.edges[0].node.site.properties
);

describe("Mutation details from object data", () => {
  it("should return a correct updated object structure", () => {
    expect(JSON.stringify(updatedObject)).toStrictEqual(JSON.stringify(updatedObjectForMetaEdit));
  });

  it("should return a correct mutation from the updated object", () => {
    const mutationString = updateObjectWithId({
      kind: deviceDetailsMocksSchema[0].kind,
      data: stringifyWithoutQuotes(updatedObject),
    });

    expect(mutationString).toEqual(mutationStringForMetaEdit);
  });
});
