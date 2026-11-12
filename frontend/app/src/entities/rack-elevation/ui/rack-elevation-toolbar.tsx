import { Button, Select, SelectItem, SelectList, SelectTrigger } from "@infrahub/ui";
import { DownloadIcon } from "lucide-react";

import { Row } from "@/shared/components/container";

import type { RackItemAttributeOption } from "@/entities/rack-elevation/domain/model/rack-elevation";

export const DISPLAY_LABEL_OPTION = "display_label";
export const NO_COLOR_OPTION = "none";

export type RackExportFormat = "svg" | "png" | "csv";

const EXPORT_FORMATS: { format: RackExportFormat; label: string }[] = [
  { format: "svg", label: "SVG" },
  { format: "png", label: "PNG" },
  { format: "csv", label: "CSV" },
];

interface AttributeSelectProps {
  label: string;
  defaultOption: { id: string; label: string };
  value: string | null;
  options: RackItemAttributeOption[];
  onChange: (value: string | null) => void;
}

function AttributeSelect({ label, defaultOption, value, options, onChange }: AttributeSelectProps) {
  const items = [defaultOption, ...options.map(({ name, label }) => ({ id: name, label }))];

  return (
    <Row>
      <span className="text-foreground-muted text-sm">{label}</span>
      <Select
        aria-label={label}
        value={value ?? defaultOption.id}
        onChange={(key) => onChange(key === defaultOption.id ? null : String(key))}
        className="w-44"
      >
        <SelectTrigger size="xs" />
        <SelectList items={items} width="content">
          {(option) => <SelectItem>{option.label}</SelectItem>}
        </SelectList>
      </Select>
    </Row>
  );
}

export interface RackElevationToolbarProps {
  labelBy: string | null;
  colorBy: string | null;
  labelOptions: RackItemAttributeOption[];
  colorOptions: RackItemAttributeOption[];
  onLabelByChange: (value: string | null) => void;
  onColorByChange: (value: string | null) => void;
  onExport: (format: RackExportFormat) => void;
}

export function RackElevationToolbar({
  labelBy,
  colorBy,
  labelOptions,
  colorOptions,
  onLabelByChange,
  onColorByChange,
  onExport,
}: RackElevationToolbarProps) {
  return (
    <Row className="flex-wrap gap-4" data-testid="rack-elevation-toolbar">
      <AttributeSelect
        label="Label"
        defaultOption={{ id: DISPLAY_LABEL_OPTION, label: "Display label" }}
        value={labelBy}
        options={labelOptions}
        onChange={onLabelByChange}
      />
      <AttributeSelect
        label="Color by"
        defaultOption={{ id: NO_COLOR_OPTION, label: "None" }}
        value={colorBy}
        options={colorOptions}
        onChange={onColorByChange}
      />
      <Row className="ml-auto">
        {EXPORT_FORMATS.map(({ format, label }) => (
          <Button
            key={format}
            variant="outline"
            size="xs"
            data-testid={`rack-export-${format}`}
            onPress={() => onExport(format)}
          >
            <DownloadIcon />
            {label}
          </Button>
        ))}
      </Row>
    </Row>
  );
}
