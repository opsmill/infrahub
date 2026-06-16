import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    // Deps discovered mid-run trigger a re-optimization reload that resets vi.mock and
    // flakes the browser tests, so anything not seen by Vite's initial scan must be
    // pre-bundled here. Two groups below:
    // - deps of @infrahub/ui and @infrahub/graph, which are workspace packages consumed
    //   as SOURCE (live symlinks), so Vite treats their imports as app source;
    // - the app's own lazily-imported deps (React.lazy / dynamic import), which the
    //   initial scan cannot see and CI's cold cache discovers mid-run.
    optimizeDeps: {
      include: [
        "react-aria-components",
        "lucide-react",
        "tailwind-variants",
        "tailwind-merge",
        "@radix-ui/react-scroll-area",
        "react-resizable-panels",
        "@graphiql/plugin-explorer",
        "@tanstack/react-query-devtools",
        "graphiql",
        "graphql",
        "jotai/utils",
        "react-dom/client",
        "react-error-boundary",
        "react-scan",
        "rehype-mermaid",
        "mermaid",
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
