/// <reference types="vite" />
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import monacoEditorPlugin from "vite-plugin-monaco-editor-esm";
import svgr from "vite-plugin-svgr";

// PROTOTYPE design-jam branch-details-repos — dev-only Save endpoint; remove with src/pages/_proto
import { designJam } from "./dev/vite-plugin-design-jam";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 8080,
    watch: {
      ignored: ["**/generated/**", "**/*.generated.ts"],
      followSymlinks: true,
    },
    fs: {
      allow: [".."],
    },
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
  },
  plugins: [
    // PROTOTYPE design-jam branch-details-repos — apply: "serve", never in a build
    designJam({ root: "../../.design" }),
    tailwindcss(),
    react(),
    babel({
      presets: [reactCompilerPreset()],
      exclude: ["**/node_modules/**", "**/generated/**", "**/*.generated.ts"],
    }),
    svgr(),
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
  resolve: {
    tsconfigPaths: true,
    // @infrahub/graph declares @xyflow/react as a peer dependency; resolve it
    // from the app's own copy so a single module instance backs the React Flow
    // context (and so the prod Docker install, which skips devDependencies,
    // can still resolve it from graph source files).
    dedupe: ["@xyflow/react"],
  },
});
