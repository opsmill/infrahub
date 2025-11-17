/// <reference types="vite" />
/// <reference types="vitest" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import monacoEditorPlugin from "vite-plugin-monaco-editor-esm";
import svgr from "vite-plugin-svgr";
import tsconfigPaths from "vite-tsconfig-paths";

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
    tailwindcss(),
    react(),
    svgr(),
    tsconfigPaths(),
    monacoEditorPlugin({
      languageWorkers: ["editorWorkerService", "json"],
      customWorkers: [
        {
          label: "graphql",
          entry: "monaco-graphql/esm/graphql.worker",
        },
      ],
    }),
  ],
  test: {
    browser: {
      enabled: true,
      provider: "playwright",
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
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**", "**/playwright-report/**"],
    globals: true,
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
      all: true,
    },
  },
});
