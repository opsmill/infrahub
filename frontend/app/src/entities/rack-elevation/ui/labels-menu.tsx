import {
  Button,
  Popover,
  PopoverDialog,
  PopoverTrigger,
  Select,
  SelectItem,
  SelectList,
  SelectTrigger,
} from "@infrahub/ui";
import { TagIcon } from "lucide-react";

import {
  HIDDEN_LABEL,
  type LabelChoices,
  type LabelOption,
  MAPPED_LABEL,
} from "@/entities/rack-elevation/domain/model/label-choice";

interface LabelsMenuProps {
  choices: LabelChoices;
  rackOptions: LabelOption[];
  itemOptions: LabelOption[];
  itemCount: number;
  onChange: (choices: LabelChoices) => void;
}

export function LabelsMenu({
  choices,
  rackOptions,
  itemOptions,
  itemCount,
  onChange,
}: LabelsMenuProps) {
  const changedCount = Object.values(choices).filter((choice) => choice !== MAPPED_LABEL).length;
  const itemSelectOptions = itemOptions.map((option) => ({
    id: option.key,
    label: option.label,
    detail: option.count < itemCount ? `${option.count} of ${itemCount}` : undefined,
  }));

  return (
    <PopoverTrigger>
      <Button size="sm" variant="outline">
        <TagIcon />
        Labels
        {changedCount > 0 && <span className="text-foreground-muted">({changedCount})</span>}
      </Button>
      <Popover placement="bottom start">
        <PopoverDialog aria-label="Labels" className="flex w-80 flex-col gap-3 p-3">
          <p className="text-foreground-muted text-xs">
            Choose which field names the rack and its objects, for example an internal name or an
            asset tag. This changes the view and exports only, not the mapping. An object without
            the field keeps its mapped label.
          </p>
          <LabelSelect
            label="Rack label"
            value={choices.rack}
            options={rackOptions.map((option) => ({ id: option.key, label: option.label }))}
            onChange={(rack) => onChange({ ...choices, rack })}
          />
          <LabelSelect
            label="Object label"
            value={choices.item}
            options={itemSelectOptions}
            onChange={(item) => onChange({ ...choices, item })}
          />
          <LabelSelect
            label="Object subtitle"
            value={choices.subtitle}
            canHide
            options={itemSelectOptions}
            onChange={(subtitle) => onChange({ ...choices, subtitle })}
          />
          {changedCount > 0 && (
            <Button
              size="xs"
              variant="ghost"
              className="self-start"
              onPress={() =>
                onChange({ rack: MAPPED_LABEL, item: MAPPED_LABEL, subtitle: MAPPED_LABEL })
              }
            >
              Reset to the mapping
            </Button>
          )}
        </PopoverDialog>
      </Popover>
    </PopoverTrigger>
  );
}

interface SelectOption {
  id: string;
  label: string;
  detail?: string;
}

function LabelSelect({
  label,
  value,
  options,
  canHide,
  onChange,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  canHide?: boolean;
  onChange: (value: string) => void;
}) {
  const items: SelectOption[] = [
    { id: MAPPED_LABEL, label: "As defined in the mapping" },
    ...(canHide ? [{ id: HIDDEN_LABEL, label: "Hidden" }] : []),
    ...options,
  ];

  return (
    <div className="flex flex-col gap-1 text-sm">
      {label}
      <Select
        aria-label={label}
        selectedKey={value}
        onSelectionChange={(key) => onChange(String(key))}
      >
        <SelectTrigger size="sm" />
        <SelectList items={items}>
          {(item) => (
            <SelectItem id={item.id} textValue={item.label}>
              {item.label}
              {item.detail && (
                <span className="ml-2 text-foreground-muted text-xs">{item.detail}</span>
              )}
            </SelectItem>
          )}
        </SelectList>
      </Select>
    </div>
  );
}
