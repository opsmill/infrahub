/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import svgr from "@svgr/rollup";
import viteTsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 8080,
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
  },
  plugins: [react(), viteTsconfigPaths(), svgr()],
  test: {
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**", "**/playwright-report/**"],
    globals: true,
    environment: "jsdom",
    coverage: {
      reporter: ["text", "lcovonly"],
      exclude: [
        "node_modules/",
        "mocks/",
        "cypress/",
        "**/**.d.ts",
        "**/tests/**",
        "**/**component-preview",
        "playwright-report/",
        "e2e/",
      ],
      all: true,
    },
  },
});
