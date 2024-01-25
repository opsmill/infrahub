import { defineConfig } from "cypress";

export default defineConfig({
  // downloadsFolder: "tests/downloads",
  // fileServerFolder: "tests/server",
  fixturesFolder: "tests/fixtures",
  screenshotsFolder: "../docs/media",
  trashAssetsBeforeRuns: false,
  // videosFolder: "tests/videos",
  retries: {
    // Configure retry attempts for `cypress run`
    // Default is 0
    runMode: 3,
    // Configure retry attempts for `cypress open`
    // Default is 0
    openMode: 0,
  },
  component: {
    devServer: {
      framework: "react",
      bundler: "vite",
    },
    specPattern: "tests/integrations/**/*.cy.{js,jsx,ts,tsx}",
    reporter: "spec",
    video: false,
    viewportHeight: 720,
    viewportWidth: 1280,
  },
  e2e: {
    // setupNodeEvents(on) {
    //   on("file:preprocessor", vitePreprocessor());
    // },
    baseUrl: "http://localhost:8000/",
    specPattern: "tests/e2e/**/*.cy.{js,jsx,ts,tsx}",
    reporter: "junit",
    reporterOptions: {
      mochaFile: "cypress/results/junit-[hash].xml",
      toConsole: true,
    },
    video: false,
    viewportHeight: 720,
    viewportWidth: 1280,
    defaultCommandTimeout: 30000,
  },
});
