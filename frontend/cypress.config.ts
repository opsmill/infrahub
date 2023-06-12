import { defineConfig } from "cypress";

export default defineConfig({
  // downloadsFolder: "tests/downloads",
  // fileServerFolder: "tests/server",
  fixturesFolder: "tests/fixtures",
  screenshotsFolder: "../docs/media/tutorial",
  trashAssetsBeforeRuns: false,
  // videosFolder: "tests/videos",
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
    baseUrl: "http://localhost:3000/",
    specPattern: "tests/e2e/**/*.cy.{js,jsx,ts,tsx}",
    reporter: "spec",
    video: false,
    viewportHeight: 720,
    viewportWidth: 1280,
  },
});
