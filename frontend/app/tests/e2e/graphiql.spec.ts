import { expect, test } from "@playwright/test";

test("/graphql - GraphiQL", async ({ page }) => {
  await test.step("navigate to GraphiQL and open new tab", async () => {
    await page.goto("/graphql");
    await expect(page.getByText("# Welcome to GraphiQL")).toBeVisible();
    await page.getByRole("button", { name: "New tab" }).click();
  });

  let retry = true;
  while (retry) {
    await expect(page.getByRole("button", { name: "Re-fetch GraphQL schema" })).toBeEnabled(); // required for autocompletion to load

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
        .pressSequentially("query {\n  Built", { delay: 500 });
    });

    if (await page.getByRole("option", { name: "BuiltinTag", exact: true }).isVisible()) {
      retry = false;
    } else {
      await page.reload();
    }
  }
});
