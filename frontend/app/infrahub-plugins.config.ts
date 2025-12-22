import type { PluginsConfig } from "@/entities/plugins/types";

/**
 * Infrahub UI Plugins Configuration
 *
 * Add plugins to enable custom UI components for specific object kinds.
 *
 * Each plugin entry specifies:
 * - package: npm package name or local path
 * - enabled: whether the plugin is active (defaults to true)
 * - overrides: optional manifest property overrides
 *
 * Example:
 * ```ts
 * const config: PluginsConfig = {
 *   plugins: [
 *     // External npm package
 *     { package: "@infrahub/plugin-device-metrics" },
 *
 *     // Local plugin
 *     { package: "./src/plugins/my-custom-plugin" },
 *
 *     // Plugin with overrides
 *     {
 *       package: "@infrahub/plugin-network-graph",
 *       overrides: { priority: 100, tabLabel: "Network View" }
 *     },
 *
 *     // Disabled plugin
 *     { package: "@infrahub/plugin-deprecated", enabled: false },
 *   ],
 * };
 * ```
 */
const config: PluginsConfig = {
  plugins: [
    // Build-time plugins can be added here
    // For runtime plugins, add them to /plugins/plugins.json instead
  ],
};

export default config;
