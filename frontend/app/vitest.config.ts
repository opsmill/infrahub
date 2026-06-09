import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    optimizeDeps: {
      // @infrahub/ui is a workspace package consumed as source (live symlink),
      // so Vite treats its imports as source and would otherwise discover these
      // runtime deps mid-run, triggering a re-optimization reload that resets
      // vi.mock and flakes the browser tests. Pre-bundle them up front.
      include: [
        "react-aria-components",
        "lucide-react",
        "tailwind-variants",
        "tailwind-merge",
        "@radix-ui/react-scroll-area",
        "react-resizable-panels",
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
