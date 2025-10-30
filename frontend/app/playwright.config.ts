import { defineConfig, devices } from "@playwright/test";

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: process.env.CI ? 3 * 60 * 1000 : 60 * 1000,
  expect: {
    timeout: process.env.CI
      ? process.env.INFRAHUB_MISC_RESPONSE_DELAY
        ? 6 * 60 * 1000
        : 3 * 60 * 1000
      : 1 * 60 * 1000,
    toHaveScreenshot: { maxDiffPixels: 5000 },
  },
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 4 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: [
    ["list"],
    ["html", { open: "never" }],
    ["junit", { outputFile: "playwright-junit.xml" }],
  ],
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: process.env.INFRAHUB_ADDRESS ?? "http://localhost:8080",

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: process.env.CI ? "retain-on-failure" : "on",
    screenshot: process.env.CI ? "only-on-failure" : "on",
    video: process.env.CI ? "retain-on-failure" : "on",
  },

  /* Configure projects for major browsers */
  projects: [
    // Setup project
    {
      name: "setup",
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
      dependencies: ["setup"],
      testIgnore: "**/docs-regression-check/**",
    },
    {
      name: "docs-regression-check",
      use: { ...devices["Desktop Chrome"], channel: "chromium" },
      dependencies: ["e2e"],
      testMatch: "**/docs-regression-check/**/*.spec.ts",
      fullyParallel: false,
      workers: 1,
    },

    // {
    //   name: "firefox",
    //   use: { ...devices["Desktop Firefox"] },
    // },

    // {
    //   name: "webkit",
    //   use: { ...devices["Desktop Safari"] },
    // },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  /* Run your local dev server before starting the tests */
  // webServer: {
  //   command: 'npm run start',
  //   url: 'http://127.0.0.1:3000',
  //   reuseExistingServer: !process.env.CI,
  // },
});
