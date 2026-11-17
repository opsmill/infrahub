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
    // Dev pre-bundling cannot load the `?worker` imports in this module, so the dev server would fail to start.
    exclude: ["graphiql/setup-workers/vite"],
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
