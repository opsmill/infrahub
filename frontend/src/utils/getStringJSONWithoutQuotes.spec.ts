import { describe, it } from "vitest";
import { C_JSON1, C_JSON1_OUTPUT, C_JSON2, C_JSON2_OUTPUT, C_JSON3, C_JSON3_OUTPUT } from "../testData/jsonSamples";
import { getStringJSONWithoutQuotes } from "./getStringJSONWithoutQuotes";

describe("Convert JSON to JSON without quotes (\") in the key names", () => {
  it("should work with nested objects", () => {
    const output1 = getStringJSONWithoutQuotes(C_JSON1);
    expect(output1).toEqual(C_JSON1_OUTPUT);
  });
  it("should work with simple array with no keys", () => {
    const output2 = getStringJSONWithoutQuotes(C_JSON2);
    expect(output2).toEqual(C_JSON2_OUTPUT);
  });
  it("should work with numbers and boolean", () => {
    const output3 = getStringJSONWithoutQuotes(C_JSON3);
    expect(output3).toEqual(C_JSON3_OUTPUT);
  });
});
