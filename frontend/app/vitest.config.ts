import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    // A dep discovered mid-run makes Vite reload the page, dropping the vi.mock() registrations
    // made before it. `entries` widens the initial scan, which browser mode otherwise seeds with
    // the test files alone, missing anything reachable only from a page no test imports.
    // `include` covers the rest; each entry resolves from frontend/app, so a dep owned by a
    // workspace package needs Vite's nested `<owner> > <dep>` form. A bare specifier that does
    // not resolve is dropped with a warning and protects nothing.
    //
    // Verifying a change here: dev/guides/frontend/writing-component-tests.md
    optimizeDeps: {
      entries: ["index.html", "src/**/*.{ts,tsx}"],
      include: [
        "@infrahub/ui > @radix-ui/react-scroll-area",
        "@infrahub/ui > react-resizable-panels",
        "@infrahub/ui > tailwind-variants",
        "@infrahub/graph > tailwind-variants",
        "infrahub-schema-visualizer > @dagrejs/dagre",
        "infrahub-schema-visualizer > html-to-image",
        "@date-fns/tz",
        "react-aria-components",
        "lucide-react",
        "tailwind-merge",
        "@graphiql/plugin-explorer",
        "@tanstack/react-query-devtools",
        "graphiql",
        "graphql",
        "jotai/utils",
        "react-dom/client",
        "react-error-boundary",
        "react-scan",
        "@headlessui/react",
        "dagre",
        "@radix-ui/react-dropdown-menu",
        "@radix-ui/react-progress",
        "react-paginate",
        "react-diff-view",
        "recharts",
        "sha1",
        "unidiff",
      ],
    },
    test: {
      browser: {
        enabled: true,
        headless: true,
        provider: playwright(),
        instances: [
          {
            browser: "chromium",
          },
        ],
        viewport: {
          width: 1280,
          height: 720,
        },
      },
      coverage: {
        provider: "v8",
        reporter: ["text", "lcovonly"],
        include: ["src/**/*.{ts,tsx}"],
        exclude: [
          "mocks/",
          "node_modules/",
          "playwright-report/",
          "tests/",
          "**/*.d.ts",
          "src/shared/api/graphql/generated/",
          "src/shared/api/rest/types.generated.ts",
        ],
      },
      exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**", "**/playwright-report/**"],
    },
  })
);
