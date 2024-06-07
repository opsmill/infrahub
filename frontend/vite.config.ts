/// <reference types="vitest" />
import federation from "@originjs/vite-plugin-federation";
import svgr from "@svgr/rollup";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import viteTsconfigPaths from "vite-tsconfig-paths";

const URL =
  // "http://localhost:8000/api/file/17d61cf7-829d-1688-3b64-c51a49b197e2/dist/assets/remoteEntry.js?content_type=text/javascript";
  // "http://localhost:4173/assets/remoteEntry.js";
  "http://localhost:8000/api/storage/object/17d66b08-8f31-53d0-3b6a-c51efe883302";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 8080,
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
  },
  plugins: [
    react(),
    viteTsconfigPaths(),
    svgr(),
    federation({
      name: "hostApp",
      remotes: {
        remoteApp: URL,
      },
      shared: ["react", "react-dom"],
    }),
  ],
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
