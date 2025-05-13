import { generateRandomString } from "./string";

describe("String utils", () => {
  test("should render a random string without numbers", async () => {
    const test = generateRandomString(10);
    const numberMatches = test.match(/\d/);

    await expect(test.length).eq(10);
    await expect(numberMatches?.length).to.be.undefined;
  });
});
