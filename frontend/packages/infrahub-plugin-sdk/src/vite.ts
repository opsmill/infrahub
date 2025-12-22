import type { Plugin } from "vite";

/**
 * Vite plugin that wraps the plugin bundle with registration code.
 * This code runs after the bundle loads and registers the plugin(s)
 * with window.InfrahubPlugins.
 */
export function infrahubPluginWrapper(): Plugin {
  return {
    name: "infrahub-plugin-wrapper",
    generateBundle(_, bundle) {
      for (const [fileName, chunk] of Object.entries(bundle)) {
        if (chunk.type === "chunk" && fileName.endsWith(".js")) {
          const registrationCode = `
// Register plugin(s) with Infrahub
(function() {
  if (!window.InfrahubRuntime) {
    console.error('[InfrahubPlugin] InfrahubRuntime not found. Plugin cannot load.');
    return;
  }
  window.InfrahubPlugins = window.InfrahubPlugins || {};
  var exported = typeof InfrahubPluginExport !== 'undefined' ? InfrahubPluginExport : {};
  if (exported.plugins) {
    exported.plugins.forEach(function(p) {
      window.InfrahubPlugins[p.manifest.id] = p;
      console.log('[InfrahubPlugin] Registered:', p.manifest.id);
    });
  } else if (exported.manifest && exported.default) {
    window.InfrahubPlugins[exported.manifest.id] = { manifest: exported.manifest, component: exported.default };
    console.log('[InfrahubPlugin] Registered:', exported.manifest.id);
  }
})();
`;
          chunk.code = chunk.code + registrationCode;
        }
      }
    },
  };
}

export interface InfrahubPluginOptions {
  /** Entry file for the plugin (default: "src/index.tsx") */
  entry?: string;
  /**
   * Plugin name - used to create output path like `built/<name>/index.js`
   * If provided, outDir becomes `built/<name>` (or `<outDir>/<name>` if outDir is also set)
   */
  name?: string;
  /** Output filename (default: "index.js") */
  fileName?: string;
  /** Output directory (default: "dist", or "built" if name is provided) */
  outDir?: string;
  /** Enable minification (default: false) */
  minify?: boolean;
  /** Enable sourcemaps (default: true) */
  sourcemap?: boolean;
  /** Additional external dependencies to exclude from bundle */
  external?: string[];
  /** Additional global mappings for external dependencies */
  globals?: Record<string, string>;
}

/** Default external dependencies provided by Infrahub runtime */
const DEFAULT_EXTERNALS = [
  "react",
  "react-dom",
  "react/jsx-runtime",
  "react/jsx-dev-runtime",
  "react-router",
  "react-router-dom",
];

/** Default global mappings for external dependencies */
const DEFAULT_GLOBALS: Record<string, string> = {
  react: "window.InfrahubRuntime.React",
  "react-dom": "window.InfrahubRuntime.ReactDOM",
  "react/jsx-runtime": "window.InfrahubRuntime.jsxRuntime",
  "react/jsx-dev-runtime": "window.InfrahubRuntime.jsxRuntime",
  "react-router": "window.InfrahubRuntime.ReactRouter",
  "react-router-dom": "window.InfrahubRuntime.ReactRouter",
};

/**
 * Creates the Vite build configuration for an Infrahub plugin.
 * Use this with Vite's `defineConfig` to set up your plugin build.
 *
 * @example Basic usage
 * ```ts
 * import { defineConfig } from "vite";
 * import react from "@vitejs/plugin-react";
 * import { infrahubPluginWrapper, createPluginConfig } from "@infrahub/plugin-sdk/vite";
 *
 * export default defineConfig({
 *   plugins: [react(), infrahubPluginWrapper()],
 *   ...createPluginConfig(),
 * });
 * ```
 *
 * @example With plugin name (outputs to built/my-plugin/index.js)
 * ```ts
 * export default defineConfig({
 *   plugins: [react(), infrahubPluginWrapper()],
 *   ...createPluginConfig({
 *     name: "my-plugin",
 *   }),
 * });
 * ```
 *
 * @example With custom options
 * ```ts
 * export default defineConfig({
 *   plugins: [react(), infrahubPluginWrapper()],
 *   ...createPluginConfig({
 *     entry: "src/main.tsx",
 *     name: "my-plugin",
 *     outDir: "plugins",  // outputs to plugins/my-plugin/index.js
 *     minify: true,
 *     // Add additional externals (e.g., a shared library from Infrahub)
 *     external: ["@apollo/client"],
 *     globals: { "@apollo/client": "window.InfrahubRuntime.ApolloClient" },
 *   }),
 * });
 * ```
 */
export function createPluginConfig(options: InfrahubPluginOptions = {}) {
  const {
    entry = "src/index.tsx",
    name,
    fileName = "index.js",
    outDir: outDirOption,
    minify = false,
    sourcemap = true,
    external = [],
    globals = {},
  } = options;

  // Compute output directory: built/<name> if name provided, otherwise outDir or "dist"
  const outDir = name
    ? `${outDirOption ?? "built"}/${name}`
    : outDirOption ?? "dist";

  return {
    define: {
      "process.env.NODE_ENV": JSON.stringify("production"),
    },
    build: {
      lib: {
        entry,
        name: "InfrahubPluginExport",
        formats: ["iife" as const],
        fileName: () => fileName,
      },
      rollupOptions: {
        external: [...DEFAULT_EXTERNALS, ...external],
        output: {
          globals: {
            ...DEFAULT_GLOBALS,
            ...globals,
          },
        },
      },
      outDir,
      emptyOutDir: true,
      minify,
      sourcemap,
    },
  };
}

/** Re-export defaults for advanced customization */
export { DEFAULT_EXTERNALS, DEFAULT_GLOBALS };
