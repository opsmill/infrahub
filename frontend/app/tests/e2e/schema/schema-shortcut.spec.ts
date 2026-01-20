import { expect, test } from "@playwright/test";

test.describe("Schema shortcut from object details", () => {
  test("should open schema modal when clicking on attribute label", async ({ page }) => {
    await page.goto("/objects/InfraDevice");
    await page.getByRole("link", { name: "atl1-edge1" }).click();

    await test.step("open schema modal from attribute", async () => {
      await page.getByTestId("object-details").getByRole("button", { name: "Name" }).click();

      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByTestId("schema-viewer")).toBeVisible();
      await expect(page.getByRole("heading", { name: "Device", exact: true })).toBeVisible();
      await expect(page.getByRole("tab", { name: "Attributes" })).toHaveAttribute(
        "aria-selected",
        "true"
      );
      await expect(page.getByText("Namename")).toBeVisible();
    });

    await test.step("close modal with close button", async () => {
      await page.getByRole("button", { name: "Close schema viewer" }).click();
      await expect(page.getByRole("dialog")).not.toBeVisible();
    });
  });

  test("should open schema modal when clicking on relationship one label", async ({ page }) => {
    await page.goto("/objects/InfraDevice");
    await page.getByRole("link", { name: "atl1-edge1" }).click();

    await test.step("open schema modal from relationship one", async () => {
      await page.getByTestId("object-details").getByRole("button", { name: "Site" }).click();

      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByTestId("schema-viewer")).toBeVisible();
      await expect(page.getByRole("tab", { name: "Relationships" })).toHaveAttribute(
        "aria-selected",
        "true"
      );
      await expect(page.getByText("Namesite")).toBeVisible();
    });

    await test.step("close modal with Escape key", async () => {
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).not.toBeVisible();
    });
  });

  test("should open schema modal when clicking on relationship many label", async ({ page }) => {
    await page.goto("/objects/InfraDevice");
    await page.getByRole("link", { name: "atl1-edge1" }).click();

    await test.step("open schema modal from relationship many", async () => {
      await page.getByTestId("object-details").getByRole("button", { name: "Tags" }).click();

      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByTestId("schema-viewer")).toBeVisible();
      await expect(page.getByRole("tab", { name: "Relationships" })).toHaveAttribute(
        "aria-selected",
        "true"
      );
      await expect(page.getByText("Nametags")).toBeVisible();
    });

    await test.step("close modal with Escape key", async () => {
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).not.toBeVisible();
    });
  });
});
