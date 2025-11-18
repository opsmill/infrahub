import { expect, test } from "@playwright/test";

test("/graphql - GraphiQL", async ({ page }) => {
  await test.step("navigate to GraphiQL and open new tab", async () => {
    await page.goto("/graphql");
    await expect(page.getByRole("button", { name: "Re-fetch GraphQL schema" })).toBeEnabled(); // required for autocompletion to load
    await expect(page.getByText("# Welcome to GraphiQL")).toBeVisible();
    await page.getByRole("button", { name: "New tab" }).click();
  });

  if (await page.getByText("# Welcome to GraphiQL").isVisible()) {
    await page
      .getByRole("region", { name: "Operation Editor" })
      .getByLabel("Editor content")
      .selectText();
  }

  await test.step("type query with partial match to trigger autocomplete", async () => {
    await page
      .getByRole("region", { name: "Operation Editor" })
      .getByLabel("Editor content")
      .pressSequentially("query {\n  Built", { delay: 1000 });
  });

  await test.step("verify BuiltinTag appears in autocomplete suggestions", async () => {
    await expect(page.getByRole("option", { name: "BuiltinTag", exact: true })).toBeVisible();
  });
});
