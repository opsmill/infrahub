import { Icon } from "@iconify-icon/react";
import { Suspense } from "react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { HomeCard } from "@/shared/components/ui/home-card";
import { classNames } from "@/shared/utils/common";

import { usePluginQuery } from "../hooks/use-plugin-query";
import type { PluginComponentProps, RegisteredPlugin } from "../types";

export interface PluginDashboardWidgetProps {
  /** The plugin to render as a dashboard widget */
  plugin: RegisteredPlugin;
}

/**
 * Maps dashboard size to Tailwind grid classes
 */
function getGridClasses(plugin: RegisteredPlugin): string {
  const { colSpan = 1, rowSpan = 2 } = plugin.manifest.dashboardSize ?? {};

  const colClasses: Record<number, string> = {
    1: "lg:col-span-1",
    2: "lg:col-span-2",
    3: "col-span-full",
  };

  const rowClasses: Record<number, string> = {
    1: "row-span-1",
    2: "row-span-2",
    3: "row-span-3",
    4: "row-span-4",
  };

  return classNames(colClasses[colSpan] ?? "lg:col-span-1", rowClasses[rowSpan] ?? "row-span-2");
}

/**
 * Renders a plugin as a dashboard widget on the homepage
 */
export function PluginDashboardWidget({ plugin }: PluginDashboardWidgetProps) {
  const { manifest, component: PluginComponent } = plugin;

  const { data, loading, error, refetch } = usePluginQuery({
    queryConfig: manifest.query,
    skip: !manifest.query,
  });

  const props: PluginComponentProps = {
    queryData: data,
    isQueryLoading: loading,
    queryError: error,
    refetchQuery: refetch,
  };

  const gridClasses = getGridClasses(plugin);

  return (
    <HomeCard className={gridClasses} data-testid={`plugin-dashboard-${manifest.id}`}>
      <HomeCard.Title>
        <div className="flex items-center gap-2">
          {manifest.icon && <Icon icon={manifest.icon} />}
          <span>{manifest.panelTitle || manifest.name}</span>
        </div>
      </HomeCard.Title>

      <HomeCard.Content className="flex-1 overflow-auto">
        <Suspense fallback={<LoadingIndicator />}>
          <PluginComponent {...props} />
        </Suspense>
      </HomeCard.Content>
    </HomeCard>
  );
}
