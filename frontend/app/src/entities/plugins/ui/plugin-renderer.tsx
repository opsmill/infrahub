import { Suspense } from "react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { ModelSchema } from "@/entities/schema/types";

import { usePluginQuery } from "../hooks/use-plugin-query";
import type { PluginComponentProps, RegisteredPlugin } from "../types";

export interface PluginRendererProps {
  /** The plugin to render */
  plugin: RegisteredPlugin;
  /** Basic object info (id, displayLabel, kind) */
  object: {
    id: string;
    displayLabel: string;
    kind: string;
  };
  /** The schema for the current object */
  schema: ModelSchema;
  /** Full object details data from the standard query */
  objectData?: unknown;
  /** Optional className for the container */
  className?: string;
}

/**
 * Renders a plugin component with its query data
 */
export function PluginRenderer({
  plugin,
  object,
  schema,
  objectData,
  className,
}: PluginRendererProps) {
  const { manifest, component: PluginComponent } = plugin;

  const { data, loading, error, refetch } = usePluginQuery({
    queryConfig: manifest.query,
    objectId: object.id,
    skip: !manifest.query,
  });

  const props: PluginComponentProps = {
    object,
    schema,
    objectData,
    queryData: data,
    isQueryLoading: loading,
    queryError: error,
    refetchQuery: refetch,
  };

  return (
    <div className={className} data-plugin-id={manifest.id}>
      <Suspense fallback={<LoadingIndicator />}>
        <PluginComponent {...props} />
      </Suspense>
    </div>
  );
}
