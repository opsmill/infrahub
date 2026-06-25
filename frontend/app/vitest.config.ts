import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    // Pre-bundle dependencies that are only reached through dynamic/conditional
    // imports (e.g. the devtools loader in src/app/devtools.tsx) so Vite's
    // dependency scanner does not discover them mid-run. When that happens in
    // browser mode, Vite re-optimizes and reloads the page ("Vite unexpectedly
    // reloaded a test"), which drops module mocks registered via vi.mock() and
    // makes mock-using tests fail intermittently (e.g.
    // "mockClear is not a function"). See vitest-dev/vitest#8447 and #7333.
    optimizeDeps: {
      include: [
        "@tanstack/react-query-devtools",
        "react-dom/client",
        "react-error-boundary",
        "react-scan",
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
