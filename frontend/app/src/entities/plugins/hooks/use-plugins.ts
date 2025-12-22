import { useEffect, useMemo, useState } from "react";

import {
  getAllPlugins,
  getDashboardPlugins,
  getPagePluginForKind,
  getPanelPluginsForKind,
  getPluginsForKind,
  getTabPluginsForKind,
  hasPluginsForKind,
} from "../registry";
import {
  areRuntimePluginsLoaded,
  loadRuntimePlugins,
} from "../runtime/plugin-loader";

/**
 * Hook that ensures runtime plugins are loaded.
 * Returns a version number that increments when plugins are loaded,
 * triggering re-renders in consuming components.
 */
export function useRuntimePlugins() {
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!areRuntimePluginsLoaded()) {
      loadRuntimePlugins().then(() => {
        // Increment version to trigger re-render with new plugins
        setVersion((v) => v + 1);
      });
    }
  }, []);

  return version;
}

/**
 * Hook to get all plugins for a specific kind
 */
export function usePluginsForKind(kind: string | undefined) {
  const version = useRuntimePlugins();
  return useMemo(() => {
    if (!kind) return [];
    return getPluginsForKind(kind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, version]);
}

/**
 * Hook to get tab plugins for a specific kind
 */
export function useTabPlugins(kind: string | undefined) {
  const version = useRuntimePlugins();
  return useMemo(() => {
    if (!kind) return [];
    return getTabPluginsForKind(kind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, version]);
}

/**
 * Hook to get panel plugins for a specific kind
 */
export function usePanelPlugins(kind: string | undefined) {
  const version = useRuntimePlugins();
  return useMemo(() => {
    if (!kind) return [];
    return getPanelPluginsForKind(kind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, version]);
}

/**
 * Hook to get page plugin for a specific kind (returns undefined if none)
 */
export function usePagePlugin(kind: string | undefined) {
  const version = useRuntimePlugins();
  return useMemo(() => {
    if (!kind) return;
    return getPagePluginForKind(kind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, version]);
}

/**
 * Hook to check if a kind has any plugins
 */
export function useHasPlugins(kind: string | undefined): boolean {
  const version = useRuntimePlugins();
  return useMemo(() => {
    if (!kind) return false;
    return hasPluginsForKind(kind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, version]);
}

/**
 * Hook to get all registered plugins
 */
export function useAllPlugins() {
  const version = useRuntimePlugins();
  return useMemo(() => getAllPlugins(), [version]);
}

/**
 * Hook to get dashboard plugins
 */
export function useDashboardPlugins() {
  const version = useRuntimePlugins();
  return useMemo(() => getDashboardPlugins(), [version]);
}
