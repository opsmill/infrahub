import { Icon } from "@iconify-icon/react";

import { Card, CardWithBorder } from "@/shared/components/ui/card";

import type { ModelSchema } from "@/entities/schema/types";

import type { RegisteredPlugin } from "../types";
import { PluginRenderer } from "./plugin-renderer";

export interface PluginPanelProps {
  /** The plugin to render as a panel */
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
}

/**
 * Renders a plugin as an expandable panel/card
 */
export function PluginPanel({ plugin, object, schema, objectData }: PluginPanelProps) {
  const { manifest } = plugin;

  return (
    <Card className="overflow-x-hidden p-0" data-testid={`plugin-panel-${manifest.id}`}>
      <CardWithBorder.Title className="border-gray-200 border-b">
        {manifest.icon && <Icon icon={manifest.icon} className="mr-2" />}
        {manifest.panelTitle || manifest.name}
      </CardWithBorder.Title>

      <PluginRenderer
        plugin={plugin}
        object={object}
        schema={schema}
        objectData={objectData}
        className="p-4"
      />
    </Card>
  );
}
