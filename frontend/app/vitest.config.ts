import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    // @infrahub/ui is consumed as workspace SOURCE, so transitive deps it pulls in (e.g.
    // lucide-react via FloatingPanel) must be pre-bundled up front. Otherwise Vite discovers
    // them mid-run and triggers a page reload that resets vi.mock(), breaking unrelated tests.
    //
    // @infrahub/graph is excluded so its components are processed as source: GraphControls'
    // `useReactFlow` import then resolves to the same @xyflow/react module that tests mock via
    // vi.mock() — a dep bundled inside an optimized chunk can't be intercepted.
    optimizeDeps: {
      include: ["lucide-react"],
      exclude: ["@infrahub/graph"],
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
