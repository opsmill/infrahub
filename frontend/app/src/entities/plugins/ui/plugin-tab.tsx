import { Icon } from "@iconify-icon/react";
import { useQueryState } from "nuqs";
import { useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-tabs";

import type { RegisteredPlugin } from "../types";

const PLUGIN_TAB_PREFIX = "plugin:";

export interface PluginTabProps {
  /** The plugin to render as a tab */
  plugin: RegisteredPlugin;
}

/**
 * Renders a tab header for a plugin
 */
export function PluginTab({ plugin }: PluginTabProps) {
  const { pathname } = useLocation();
  const [qspTab] = useQueryState(QSP.TAB);
  const tabId = `${PLUGIN_TAB_PREFIX}${plugin.manifest.id}`;
  const isActive = qspTab === tabId;

  return (
    <ObjectDetailsTab
      isActive={isActive}
      to={constructPath(pathname, [{ name: QSP.TAB, value: tabId }])}
    >
      {plugin.manifest.icon && <Icon icon={plugin.manifest.icon} className="mr-1" />}
      {plugin.manifest.tabLabel || plugin.manifest.name}
    </ObjectDetailsTab>
  );
}

/**
 * Check if the current tab is a plugin tab
 */
export function isPluginTab(tabValue: string | null): boolean {
  return tabValue?.startsWith(PLUGIN_TAB_PREFIX) ?? false;
}

/**
 * Extract the plugin ID from a tab value
 */
export function getPluginIdFromTab(tabValue: string | null): string | null {
  if (!tabValue?.startsWith(PLUGIN_TAB_PREFIX)) return null;
  return tabValue.slice(PLUGIN_TAB_PREFIX.length);
}

/**
 * Get the tab value for a plugin
 */
export function getPluginTabValue(pluginId: string): string {
  return `${PLUGIN_TAB_PREFIX}${pluginId}`;
}
