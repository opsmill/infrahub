import { defineConfig } from "cypress";
import vitePreprocessor from "cypress-vite";

export default defineConfig({
  // downloadsFolder: "tests/downloads",
  // fileServerFolder: "tests/server",
  fixturesFolder: "tests/fixtures",
  // screenshotsFolder: "tests/screenshots",
  // videosFolder: "tests/videos",
  component: {
    devServer: {
      framework: "react",
      bundler: "vite",
    },
    reporter: "spec",
    video: false,
  },
  e2e: {
    setupNodeEvents(on) {
      on("file:preprocessor", vitePreprocessor());
    },
    reporter: "spec",
    video: false,
  },
});
