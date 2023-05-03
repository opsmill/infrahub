import { defineConfig } from "cypress";

export default defineConfig({
  component: {
    devServer: {
      framework: "create-react-app",
      bundler: "webpack",
    },
    reporter: "spec",
  },
  e2e: {
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    reporter: "spec",
  },
});
