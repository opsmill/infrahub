import { playwright } from "@vitest/browser-playwright";
import { defineConfig, mergeConfig } from "vitest/config";

import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      browser: {
        enabled: true,
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
        reporter: ["text", "lcovonly"],
        exclude: [
          "node_modules/",
          "mocks/",
          "**/**.d.ts",
          "**/tests/**",
          "**/**component-preview",
          "playwright-report/",
          "e2e/",
        ],
      },
      exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**", "**/playwright-report/**"],
    },
  })
);
