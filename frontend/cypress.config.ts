import { defineConfig } from "cypress";
import vitePreprocessor from "cypress-vite";

export default defineConfig({
  component: {
    devServer: {
      framework: "react",
      bundler: "vite",
    },
    reporter: "spec",
    defaultCommandTimeout: 10000,
  },
  e2e: {
    setupNodeEvents(on) {
      on("file:preprocessor", vitePreprocessor());
    },
    reporter: "spec",
    defaultCommandTimeout: 10000,
  },
});
