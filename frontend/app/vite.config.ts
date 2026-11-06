/// <reference types="vite" />
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import svgr from "vite-plugin-svgr";

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
    tailwindcss(),
    react(),
    babel({
      presets: [reactCompilerPreset()],
      exclude: ["**/node_modules/**", "**/generated/**", "**/*.generated.ts"],
    }),
    svgr(),
  ],
  optimizeDeps: {
    // Pre-bundling would hide their `?worker` imports from Vite, so the Monaco workers would not be emitted.
    exclude: ["graphiql/setup-workers/vite", "@graphiql/react/setup-workers/vite"],
  },
  resolve: {
    tsconfigPaths: true,
    // @infrahub/graph declares @xyflow/react as a peer dependency; resolve it
    // from the app's own copy so a single module instance backs the React Flow
    // context (and so the prod Docker install, which skips devDependencies,
    // can still resolve it from graph source files).
    dedupe: ["@xyflow/react"],
  },
});
