// Import plugins from the virtual module (generated at build time)
// This import is resolved by the vite-plugin-infrahub-plugins at build time
import { plugins as buildTimePlugins } from "virtual:infrahub-plugins";

import type { PluginPosition, RegisteredPlugin } from "./types";
import { getRuntimePlugins } from "./runtime/plugin-loader";

/**
 * Get all registered plugins (build-time + runtime)
 */
export function getAllPlugins(): RegisteredPlugin[] {
  return [...buildTimePlugins, ...getRuntimePlugins()];
}

/**
 * Get plugins that apply to a specific kind
 */
export function getPluginsForKind(kind: string): RegisteredPlugin[] {
  return getAllPlugins().filter((plugin) => plugin.manifest.kinds.includes(kind));
}

/**
 * Get plugins for a specific kind and position
 */
export function getPluginsForKindAndPosition(
  kind: string,
  position: PluginPosition
): RegisteredPlugin[] {
  return getAllPlugins().filter(
    (plugin) => plugin.manifest.kinds.includes(kind) && plugin.manifest.position === position
  );
}

/**
 * Get tab plugins for a specific kind, sorted by priority
 */
export function getTabPluginsForKind(kind: string): RegisteredPlugin[] {
  return getPluginsForKindAndPosition(kind, "tab").sort(
    (a, b) => (b.manifest.priority ?? 0) - (a.manifest.priority ?? 0)
  );
}

/**
 * Get panel plugins for a specific kind, sorted by priority
 */
export function getPanelPluginsForKind(kind: string): RegisteredPlugin[] {
  return getPluginsForKindAndPosition(kind, "panel").sort(
    (a, b) => (b.manifest.priority ?? 0) - (a.manifest.priority ?? 0)
  );
}

/**
 * Get page plugins for a specific kind (should be at most one)
 */
export function getPagePluginForKind(kind: string): RegisteredPlugin | undefined {
  const pagePlugins = getPluginsForKindAndPosition(kind, "page").sort(
    (a, b) => (b.manifest.priority ?? 0) - (a.manifest.priority ?? 0)
  );
  return pagePlugins[0];
}

/**
 * Check if a kind has any plugins
 */
export function hasPluginsForKind(kind: string): boolean {
  return getAllPlugins().some((plugin) => plugin.manifest.kinds.includes(kind));
}

/**
 * Get a plugin by its ID
 */
export function getPluginById(id: string): RegisteredPlugin | undefined {
  return getAllPlugins().find((plugin) => plugin.manifest.id === id);
}

/**
 * Get dashboard plugins, sorted by priority
 */
export function getDashboardPlugins(): RegisteredPlugin[] {
  return getAllPlugins()
    .filter((plugin) => plugin.manifest.position === "dashboard")
    .sort((a, b) => (b.manifest.priority ?? 0) - (a.manifest.priority ?? 0));
}
