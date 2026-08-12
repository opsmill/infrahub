import { defineConfig } from "oxfmt";

export default defineConfig({
  sortImports: {
    newlinesBetween: true,
    groups: [
      "type-import",
      ["value-builtin", "value-external"],
      "type-internal",
      "value-internal",
      ["type-parent", "type-sibling", "type-index"],
      ["value-parent", "value-sibling", "value-index"],
      "unknown",
    ],
  },
  sortPackageJson: {
    sortScripts: true,
  },
});
