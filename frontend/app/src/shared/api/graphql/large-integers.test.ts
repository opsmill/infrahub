import { describe, expect, it } from "vitest";

import { quoteLargeIntegers } from "./large-integers";

describe("quoteLargeIntegers", () => {
  it("quotes integers a JavaScript number cannot hold exactly", () => {
    // GIVEN
    const json = '{"end":9223372036854775807,"start":-9007199254740993,"list":[9007199254740993]}';

    // WHEN
    const parsed = JSON.parse(quoteLargeIntegers(json));

    // THEN
    expect(parsed).toEqual({
      end: "9223372036854775807",
      start: "-9007199254740993",
      list: ["9007199254740993"],
    });
  });

  it("leaves safe integers, decimals, exponents and strings unchanged", () => {
    // GIVEN
    const json =
      '{"a":9007199254740991,"b":12345678901234567.5,"c":1e12345678901234567,"d":0.12345678901234567,"e":"x: 9223372036854775807, \\"9223372036854775807\\""}';

    // WHEN
    const quoted = quoteLargeIntegers(json);

    // THEN
    expect(quoted).toBe(json);
  });
});
