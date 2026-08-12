import type { Page } from "@playwright/test";

export const saveScreenshotForDocs = async (page: Page, filename: string) => {
  if (!process.env.UPDATE_DOCS_SCREENSHOTS) return;

  await page.waitForLoadState("networkidle");
  await page.screenshot({
    path: `../../docs/docs/media/${filename}.png`,
    animations: "disabled",
  });
};

export const generateRandomBranchName = (prefix?: string) => {
  return `${prefix ?? ""}${Math.random().toString(36).substring(2, 15)}`;
};

export function getDataTableRow(page: Page, name: string) {
  return page
    .getByTestId("data-table-row")
    .filter({ has: page.getByRole("link", { name, exact: true }) });
}
