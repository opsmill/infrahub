/**
 * Runtime Plugin Loader
 *
 * Loads plugins at runtime from the /assets/plugins directory.
 * Plugins are loaded via <script> tags and register themselves
 * with window.InfrahubPlugins.
 *
 * Directory structure:
 * /assets/plugins/
 *   plugins.json          # Config listing enabled plugins
 *   my-plugin/
 *     index.js            # Bundled plugin code
 *     manifest.json       # Optional: plugin metadata
 */

import type { RegisteredPlugin, PluginManifest } from "../types";

// Ensure runtime is initialized
import "./infrahub-runtime";

export interface PluginConfig {
  /** Plugin directory name */
  id: string;
  /** Whether the plugin is enabled (defaults to true) */
  enabled?: boolean;
  /** Optional manifest overrides */
  overrides?: Partial<PluginManifest>;
}

export interface PluginsJson {
  plugins: PluginConfig[];
}

/** Cache for loaded plugins */
let loadedPlugins: RegisteredPlugin[] | null = null;
let loadingPromise: Promise<RegisteredPlugin[]> | null = null;

/**
 * Get the base URL for plugins directory
 */
function getPluginsBaseUrl(): string {
  // Plugins are served from /assets/plugins/ which is already
  // configured as a static file route in the backend
  return "/assets/plugins";
}

/**
 * Load a script dynamically and wait for it to execute
 */
function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    // Check if script is already loaded
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }

    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load plugin script: ${src}`));
    document.head.appendChild(script);
  });
}

/**
 * Fetch the plugins configuration
 */
async function fetchPluginsConfig(): Promise<PluginsJson | null> {
  const baseUrl = getPluginsBaseUrl();
  const url = `${baseUrl}/plugins.json`;

  console.log("[PluginLoader] Fetching plugins config from:", url);

  try {
    const response = await fetch(url);
    if (!response.ok) {
      if (response.status === 404) {
        console.log("[PluginLoader] No plugins.json found, no runtime plugins to load");
        return null;
      }
      throw new Error(`HTTP ${response.status}`);
    }
    const config = await response.json();
    console.log("[PluginLoader] Found plugins config:", config);
    return config;
  } catch (error) {
    console.warn("[PluginLoader] Failed to fetch plugins.json:", error);
    return null;
  }
}

/**
 * Load a single plugin by ID
 */
async function loadPlugin(config: PluginConfig): Promise<RegisteredPlugin[]> {
  const baseUrl = getPluginsBaseUrl();
  const pluginUrl = `${baseUrl}/${config.id}/index.js`;

  console.log(`[PluginLoader] Loading plugin from: ${pluginUrl}`);

  // Record which plugins exist before loading
  const existingIds = new Set(Object.keys(window.InfrahubPlugins));
  console.log(`[PluginLoader] Existing plugin IDs before load:`, Array.from(existingIds));

  try {
    await loadScript(pluginUrl);

    console.log(`[PluginLoader] Script loaded, checking window.InfrahubPlugins:`, Object.keys(window.InfrahubPlugins));

    // Find newly registered plugins
    const newPlugins: RegisteredPlugin[] = [];
    for (const [id, plugin] of Object.entries(window.InfrahubPlugins)) {
      if (!existingIds.has(id)) {
        console.log(`[PluginLoader] Found new plugin: ${id}`, plugin.manifest);
        // Apply any overrides from config
        const manifest = {
          ...(plugin.manifest as PluginManifest),
          ...config.overrides,
        };
        newPlugins.push({
          manifest,
          component: plugin.component as RegisteredPlugin["component"],
        });
      }
    }

    if (newPlugins.length === 0) {
      console.warn(`[PluginLoader] Plugin ${config.id} loaded but didn't register any plugins`);
      console.warn(`[PluginLoader] window.InfrahubPlugins contents:`, window.InfrahubPlugins);
    } else {
      console.log(`[PluginLoader] Registered ${newPlugins.length} plugin(s) from ${config.id}`);
    }

    return newPlugins;
  } catch (error) {
    console.error(`[PluginLoader] Failed to load plugin ${config.id}:`, error);
    return [];
  }
}

/**
 * Load all runtime plugins
 * Returns cached result if already loaded
 */
export async function loadRuntimePlugins(): Promise<RegisteredPlugin[]> {
  console.log("[PluginLoader] loadRuntimePlugins called");

  // Return cached plugins if available
  if (loadedPlugins !== null) {
    console.log("[PluginLoader] Returning cached plugins:", loadedPlugins.length);
    return loadedPlugins;
  }

  // Return existing promise if load is in progress
  if (loadingPromise !== null) {
    console.log("[PluginLoader] Load already in progress, waiting...");
    return loadingPromise;
  }

  console.log("[PluginLoader] Starting plugin load...");

  // Start loading
  loadingPromise = (async () => {
    const config = await fetchPluginsConfig();

    if (!config || config.plugins.length === 0) {
      console.log("[PluginLoader] No plugins configured");
      loadedPlugins = [];
      return loadedPlugins;
    }

    // Load all enabled plugins in parallel
    const enabledPlugins = config.plugins.filter((p) => p.enabled !== false);
    console.log(`[PluginLoader] Loading ${enabledPlugins.length} enabled plugin(s)`);
    const results = await Promise.all(enabledPlugins.map(loadPlugin));

    // Flatten results
    loadedPlugins = results.flat();

    console.log(`[PluginLoader] Finished loading ${loadedPlugins.length} runtime plugin(s)`);
    console.log("[PluginLoader] Loaded plugins:", loadedPlugins.map(p => p.manifest.id));

    return loadedPlugins;
  })();

  return loadingPromise;
}

/**
 * Get all loaded runtime plugins (synchronous, returns empty if not loaded yet)
 */
export function getRuntimePlugins(): RegisteredPlugin[] {
  return loadedPlugins ?? [];
}

/**
 * Check if runtime plugins have been loaded
 */
export function areRuntimePluginsLoaded(): boolean {
  return loadedPlugins !== null;
}

/**
 * Force reload of runtime plugins (clears cache)
 */
export async function reloadRuntimePlugins(): Promise<RegisteredPlugin[]> {
  loadedPlugins = null;
  loadingPromise = null;

  // Clear registered plugins
  if (typeof window !== "undefined") {
    window.InfrahubPlugins = {};
  }

  return loadRuntimePlugins();
}
