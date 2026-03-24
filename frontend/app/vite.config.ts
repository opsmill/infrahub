/// <reference types="vite" />
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import monacoEditorPlugin from "vite-plugin-monaco-editor-esm";
import svgr from "vite-plugin-svgr";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    port: 8080,
    watch: {
      ignored: [
        "**/graphql-env.d.ts",
        "**/graphql-cache.d.ts",
        "**/graphql/generated/**",
        "**/rest/types.generated.ts",
        "**/playwright-report/**",
      ],
    },
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
  },
  plugins: [
    tailwindcss(),
    react(),
    babel({
      presets: [reactCompilerPreset()],
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
  },
});
