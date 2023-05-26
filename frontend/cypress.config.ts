import { defineConfig } from "cypress";

export default defineConfig({
  component: {
    devServer: {
      framework: "react",
      bundler: "vite",
    },
    reporter: "spec",
  },
  e2e: {
    // setupNodeEvents(on, config) {
    //   // implement node event listeners here
    // },
    reporter: "spec",
  },
});
