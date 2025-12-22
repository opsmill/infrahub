/// <reference types="vite" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import monacoEditorPlugin from "vite-plugin-monaco-editor-esm";
import svgr from "vite-plugin-svgr";
import tsconfigPaths from "vite-tsconfig-paths";

import { infrahubPlugins } from "./plugins/vite-plugin-infrahub-plugins";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 8080,
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
  },
  resolve: {
    // Dedupe shared dependencies to ensure plugins use the same instances as the main app
    // This is required for file: linked packages and monorepo setups
    dedupe: [
      "react",
      "react-dom",
      "react/jsx-runtime",
      "react/jsx-dev-runtime",
      "react-router",
      "react-router-dom",
    ],
  },
  plugins: [
    tailwindcss(),
    react(),
    svgr(),
    tsconfigPaths(),
    infrahubPlugins(),
    monacoEditorPlugin({
      languageWorkers: ["editorWorkerService", "json"],
      customWorkers: [
        {
          label: "graphql",
          entry: "monaco-graphql/esm/graphql.worker.js",
        },
      ],
      publicPath: "assets/monaco-editor",
    }),
  ],
});
