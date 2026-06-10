import { defineConfig } from "oxlint";

// Bug-catching categories only (matching the app's biome philosophy): style and
// opinionated rules are oxfmt's / code review's job, not the linter's.
export default defineConfig({
  env: {
    browser: true,
  },
  categories: {
    correctness: "error",
    perf: "error",
    suspicious: "error",
  },
  plugins: ["oxc", "typescript", "react", "react-perf", "jsx-a11y", "vitest", "unicorn"],
  rules: {
    "eslint/no-console": ["error", { allow: ["error"] }],
    // The React Compiler memoizes; inline values as props are not a re-render hazard here.
    "react-perf/jsx-no-new-array-as-prop": "off",
    "react-perf/jsx-no-new-function-as-prop": "off",
    "react-perf/jsx-no-new-object-as-prop": "off",
    "react/react-in-jsx-scope": "off",
  },
});
