import type { Page } from "@playwright/test";

export const saveScreenshotForDocs = async (page: Page, filename: string) => {
  if (!process.env.UPDATE_DOCS_SCREENSHOTS) return;

  await page.waitForLoadState("networkidle");
  await page.screenshot({
    path: `../../docs/docs/media/${filename}.png`,
    animations: "disabled",
  });
};

// Hex, not base36: Playwright's `name` option substring-matches, and the branch selector renders
// the current branch name on every page, so a suffix that spells a word the suites locate by makes
// that locator match two elements and the test dies with a strict-mode violation. A base36 suffix
// once produced `object-relationshipsaveyj8q5g6r`, whose "save" collided with
// getByRole("button", { name: "Save" }). No name these suites locate by is spellable in hex.
// Keep in sync with generate_random_branch_name in tests/e2e/helpers.py.
export const generateRandomBranchName = (prefix?: string) => {
  return `${prefix ?? ""}${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
};

export function getDataTableRow(page: Page, name: string) {
  return page
    .getByTestId("data-table-row")
    .filter({ has: page.getByRole("link", { name, exact: true }) });
}
