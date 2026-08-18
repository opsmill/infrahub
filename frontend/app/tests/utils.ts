import type { Page } from "@playwright/test";

export const saveScreenshotForDocs = async (page: Page, filename: string) => {
  if (!process.env.UPDATE_DOCS_SCREENSHOTS) return;

  // The published documentation is written against the light theme, while a development stack now
  // starts dark. Without pinning it here, a regeneration run would quietly turn every screenshot in
  // the docs dark.
  await page.evaluate(() => {
    localStorage.setItem("infrahub.theme.choice", "light");
    document.documentElement.classList.remove("dark");
  });

  // The flip triggers observer-driven re-renders (diagrams and the sandbox rebuild whole subtrees),
  // so settle the network and let two frames paint before capturing.
  await page.waitForLoadState("networkidle");
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  );

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
