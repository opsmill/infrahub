import { describe, expect, it } from "vitest";
import { updateObjectWithId } from "../../../src/graphql/mutations/objects/updateObjectWithId";
import getFormStructureForCreateEdit from "../../../src/utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../../src/utils/getMutationDetailsFromFormData";
import { stringifyWithoutQuotes } from "../../../src/utils/string";
import {
  accountTokenDetailsMocksDataWithDate,
  accountTokenDetailsMocksSchema,
  accountTokenDetailsUpdateDataMocksData,
  accountTokenDetailsUpdatesMocksData,
  accountTokenFormStructure,
  accountTokenId,
  accountTokenMutationMocksData,
} from "../../mocks/data/accountToken";
import { genericsMocks } from "../../mocks/data/generics";

describe("Form structure and object update", () => {
  it("should return a correct form structure", () => {
    const calculatedAttributes = getFormStructureForCreateEdit(
      accountTokenDetailsMocksSchema[0],
      accountTokenDetailsMocksSchema,
      genericsMocks,
      [],
      accountTokenDetailsMocksDataWithDate.CoreAccount.edges[0].node,
      {}
    );

    expect(JSON.stringify(calculatedAttributes)).toStrictEqual(
      JSON.stringify(accountTokenFormStructure)
    );
  });

  it("should return a correct updated object for mutation", () => {
    const updatedObject = getMutationDetailsFromFormData(
      accountTokenDetailsMocksSchema[0],
      accountTokenDetailsUpdateDataMocksData,
      "update",
      accountTokenDetailsMocksDataWithDate.CoreAccount.edges[0].node
    );

    expect(JSON.stringify(updatedObject)).toStrictEqual(
      JSON.stringify(accountTokenDetailsUpdatesMocksData)
    );

    const mutationString = updateObjectWithId({
      kind: accountTokenDetailsMocksSchema[0].kind,
      data: stringifyWithoutQuotes({
        id: accountTokenId,
        ...updatedObject,
      }),
    });

    expect(mutationString).toStrictEqual(accountTokenMutationMocksData);
  });
});
