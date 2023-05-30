/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import svgrPlugin from "vite-plugin-svgr";
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
  plugins: [react(), viteTsconfigPaths(), svgrPlugin()],
  test: {
    globals: true,
    environment: "jsdom",
    coverage: {
      reporter: ["text", "lcovonly"],
      exclude: [
        "node_modules/",
        "mocks/",
        "cypress/",
        "**/**.d.ts",
        "**/__tests__/**",
        "**/**component-preview",
      ],
      all: true,
    },
  },
});
