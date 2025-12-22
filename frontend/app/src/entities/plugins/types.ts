import type { ComponentType } from "react";

import type { ModelSchema } from "@/entities/schema/types";

/**
 * Position where the plugin component will be rendered
 * - tab: Rendered as a tab in object detail view
 * - panel: Rendered as a panel in object detail sidebar
 * - page: Replaces the entire object detail page
 * - dashboard: Rendered as a widget on the homepage dashboard
 */
export type PluginPosition = "tab" | "panel" | "page" | "dashboard";

/**
 * Dashboard widget size configuration
 */
export interface DashboardWidgetSize {
  /** Number of grid columns (1-3, default: 1) */
  colSpan?: 1 | 2 | 3;
  /** Number of grid rows (1-4, default: 2) */
  rowSpan?: 1 | 2 | 3 | 4;
}

/**
 * Query configuration for a plugin
 * Supports both saved queries (by name) and inline query strings
 */
export type PluginQueryConfig = { type: "saved"; name: string } | { type: "inline"; query: string };

/**
 * Plugin manifest that defines how a plugin should be loaded and where it appears
 */
export interface PluginManifest {
  /** Unique identifier for the plugin */
  id: string;
  /** Display name for the plugin */
  name: string;
  /** The kind(s) this plugin applies to (e.g., "InfraDevice", "CoreRepository"). Empty array for dashboard plugins. */
  kinds: string[];
  /** Where the plugin component should appear */
  position: PluginPosition;
  /** Optional GraphQL query configuration */
  query?: PluginQueryConfig;
  /** Optional tab label (used when position is "tab") */
  tabLabel?: string;
  /** Optional panel title (used when position is "panel" or "dashboard") */
  panelTitle?: string;
  /** Optional icon (iconify icon name) */
  icon?: string;
  /** Optional priority for ordering (higher = appears first) */
  priority?: number;
  /** Dashboard widget size (used when position is "dashboard") */
  dashboardSize?: DashboardWidgetSize;
}

/**
 * Props passed to plugin components at runtime
 */
export interface PluginComponentProps<TQueryData = unknown, TObjectData = unknown> {
  /** Basic object info (id, displayLabel, kind) - undefined for dashboard plugins */
  object?: {
    id: string;
    displayLabel: string;
    kind: string;
  };
  /** The schema for the current object - undefined for dashboard plugins */
  schema?: ModelSchema;
  /** Full object details data (all attributes and relationships from the standard query) */
  objectData?: TObjectData;
  /** Data from the plugin's custom query (if configured in manifest) */
  queryData?: TQueryData;
  /** Whether the custom query is loading */
  isQueryLoading?: boolean;
  /** Error from the custom query (if any) */
  queryError?: Error;
  /** Function to refetch the custom query */
  refetchQuery?: () => void;
}

/**
 * Props passed specifically to dashboard plugin components
 */
export interface DashboardPluginProps<TQueryData = unknown> {
  /** Data from the plugin's custom query (if configured in manifest) */
  queryData?: TQueryData;
  /** Whether the custom query is loading */
  isQueryLoading?: boolean;
  /** Error from the custom query (if any) */
  queryError?: Error;
  /** Function to refetch the custom query */
  refetchQuery?: () => void;
}

/**
 * A registered plugin with its manifest and component
 */
export interface RegisteredPlugin {
  manifest: PluginManifest;
  component: ComponentType<PluginComponentProps>;
}

/**
 * Plugin configuration for a single plugin in infrahub-plugins.config.ts
 */
export interface PluginConfig {
  /** npm package name or local path */
  package: string;
  /** Optional custom manifest overrides */
  overrides?: Partial<PluginManifest>;
  /** Whether the plugin is enabled (defaults to true) */
  enabled?: boolean;
}

/**
 * Root configuration for infrahub-plugins.config.ts
 */
export interface PluginsConfig {
  plugins: PluginConfig[];
}

/**
 * Virtual module type for plugin registry (generated at build time)
 */
export interface PluginRegistryModule {
  plugins: RegisteredPlugin[];
}

/**
 * Expected export shape from a plugin package
 */
export interface InfrahubPluginExport {
  manifest: PluginManifest;
  default: ComponentType<PluginComponentProps>;
}
