import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
    // @vitejs/plugin-react@6 dropped its bundled Babel, so the React Compiler must run via
    // @rolldown/plugin-babel + reactCompilerPreset (matches frontend/app/vite.config.ts).
    babel({
      presets: [reactCompilerPreset()],
      exclude: ["**/node_modules/**"],
    }),
  ],
});
