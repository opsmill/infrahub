// Screenshot every scn- branch page and check its expected state.
// Usage: node verify.mjs [outDir]
// Env: FRONTEND_URL (default http://localhost:8080), PLAYWRIGHT_MODULE (path to the playwright package),
//      INFRAHUB_USERNAME / INFRAHUB_PASSWORD (default admin / infrahub).
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const playwrightModule =
  process.env.PLAYWRIGHT_MODULE ??
  resolve(here, "../../../../frontend/app/node_modules/playwright/index.js");
const { chromium } = createRequire(import.meta.url)(playwrightModule);

const base = (process.env.FRONTEND_URL ?? "http://localhost:8080").replace(/\/$/, "");
const out = resolve(process.argv[2] ?? join(here, "screenshots"));
mkdirSync(out, { recursive: true });

const count = (text, needle) => text.split(needle).length - 1;
// Set SCN_UNREACHABLE=1 after `seed.py up --with-unreachable`.
const unreachable = process.env.SCN_UNREACHABLE === "1";

const scenarios = [
  {
    branch: "scn-all-clear",
    checks: (t) => ({
      noImportBand: !t.includes("import failed"),
      repoPager: /Showing 1 to 10 of 1\d/.test(t),
      readOnlyTag: t.includes("Read-only"),
    }),
  },
  { branch: "scn-all-clear", query: "?repositories_page=2", shot: "scn-all-clear-repos-page-2", checks: (t) => ({ page2: /Showing 11 to 1\d of 1\d/.test(t) }) },
  {
    branch: "scn-import-error",
    checks: (t) => ({
      band: t.includes("scn-fixtures — import failed"),
      viewTaskLog: t.includes("View task log"),
      oneImportBand: count(t, "— import failed") === 1,
      errorLine: t.includes("queries/scn-fixtures-missing.gql"),
      ...(unreachable && { amberBands: count(t, "Infrahub can't fetch new commits") === 2 }),
    }),
  },
  {
    branch: "scn-import-error",
    shot: "scn-import-error-dark",
    colorScheme: "dark",
    checks: (t) => ({ band: t.includes("import failed") }),
  },
  {
    branch: "scn-many-errors",
    checks: (t) => ({
      threeBands: count(t, "— import failed") === 3,
      moreLine: /\d+ more repositor(y|ies) with errors/.test(t),
      showAll: t.includes("Show all"),
    }),
    after: async (page) => {
      await page.getByRole("button", { name: "Show all" }).click();
      await page.waitForTimeout(1500);
      return {
        name: "scn-many-errors-expanded",
        checks: (t) => ({
          fiveBands: count(t, "— import failed") === 5,
          collapse: t.includes("Collapse"),
          detailsNotFound: t.includes("The error details couldn't be found"),
          ...(unreachable && { amberBands: count(t, "Infrahub can't fetch new commits") === 2 }),
        }),
      };
    },
  },
  {
    branch: "scn-generator-failed",
    checks: (t) => ({ failedCount: /\d+ failed/.test(t), taskPager: /Showing 1 to 10 of \d+/.test(t) }),
  },
  { branch: "scn-many-tasks", checks: (t) => ({ taskPager: /Showing 1 to 10 of \d+/.test(t) }) },
  { branch: "scn-many-tasks", query: "?tasks_page=2", shot: "scn-many-tasks-tasks-page-2", checks: (t) => ({ tasksPage2: /Showing 11 to \d+ of \d+/.test(t) }) },
  {
    branch: "scn-no-git",
    checks: (t) => ({
      // Sync with Git off lists read-only repositories only; scn-readonly is always there.
      readOnlyOnly: t.includes("scn-readonly") && !t.includes("scn-repo-01"),
    }),
  },
  // Set SCN_MANY_BRANCHES=1 after `seed.py up --many-branches`.
  ...(process.env.SCN_MANY_BRANCHES === "1"
    ? [
        { branch: "scn-b-04", checks: (t) => ({ band: t.includes("scn-fixtures — import failed") }) },
        { branch: "scn-b-02", checks: (t) => ({ noImportBand: !t.includes("— import failed") }) },
      ]
    : []),
];

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 2600 } });
const page = await context.newPage();

await page.goto(`${base}/login`);
await page.getByText("Log in with your credentials").click();
await page.getByLabel("Username").fill(process.env.INFRAHUB_USERNAME ?? "admin");
await page.getByLabel("Password").fill(process.env.INFRAHUB_PASSWORD ?? "infrahub");
await page.getByRole("button", { name: "Log in", exact: true }).click();
await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 15000 });

const results = [];
for (const scenario of scenarios) {
  const name = scenario.shot ?? scenario.branch;
  await page.emulateMedia({ colorScheme: scenario.colorScheme ?? "light" });
  await page.goto(`${base}/branches/${scenario.branch}${scenario.query ?? ""}`);
  await page.getByText("Git repositories").first().waitFor({ timeout: 15000 });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1500);
  const text = await page.locator("body").innerText();
  await page.screenshot({ path: join(out, `${name}.png`), fullPage: true });
  results.push({ name, url: page.url(), checks: scenario.checks(text) });
  if (scenario.after) {
    const next = await scenario.after(page);
    const afterText = await page.locator("body").innerText();
    await page.screenshot({ path: join(out, `${next.name}.png`), fullPage: true });
    results.push({ name: next.name, url: page.url(), checks: next.checks(afterText) });
  }
  writeFileSync(join(out, `${name}.txt`), text);
}
await browser.close();

writeFileSync(join(out, "results.json"), JSON.stringify(results, null, 2));
for (const r of results) {
  const failed = Object.entries(r.checks).filter(([, ok]) => !ok).map(([k]) => k);
  console.log(`${failed.length ? "FAIL" : "ok  "} ${r.name.padEnd(30)} ${failed.length ? `failed: ${failed.join(", ")}` : ""}`);
}
console.log(`screenshots in ${out}`);
