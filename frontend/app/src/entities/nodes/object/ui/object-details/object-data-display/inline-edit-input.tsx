import { formatISO } from "date-fns";

import { JsonEditor } from "@/shared/components/editor/json/json-editor";
import { MarkdownEditor } from "@/shared/components/editor/markdown";
import { Checkbox } from "@/shared/components/inputs/checkbox";
import { ColorPicker } from "@/shared/components/inputs/color-picker";
import { DatePicker } from "@/shared/components/inputs/date-picker";
import { Dropdown } from "@/shared/components/inputs/dropdown";
import { List } from "@/shared/components/list";
import { Input } from "@/shared/components/ui/input";

import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeSchema } from "@/entities/schema/types";

export interface InlineEditInputProps {
  attributeSchema: AttributeSchema;
  value: unknown;
  onChange: (value: unknown) => void;
  onKeyDown?: (e: React.KeyboardEvent) => void;
  autoFocus?: boolean;
  disabled?: boolean;
}

export function InlineEditInput({
  attributeSchema,
  value,
  onChange,
  onKeyDown,
  autoFocus = true,
  disabled,
}: InlineEditInputProps) {
  const kind = attributeSchema.kind;

  switch (kind) {
    case ATTRIBUTE_KIND.TEXT:
    case ATTRIBUTE_KIND.EMAIL:
    case ATTRIBUTE_KIND.URL:
    case ATTRIBUTE_KIND.MAC_ADDRESS:
    case ATTRIBUTE_KIND.FILE:
    case ATTRIBUTE_KIND.IP_HOST:
    case ATTRIBUTE_KIND.IP_NETWORK:
    case ATTRIBUTE_KIND.ANY:
      return (
        <Input
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          autoFocus={autoFocus}
          disabled={disabled}
          className="w-full"
        />
      );

    case ATTRIBUTE_KIND.NUMBER:
    case ATTRIBUTE_KIND.BANDWIDTH:
      return (
        <Input
          type="number"
          value={value as number | ""}
          onChange={(e) => {
            const numValue = e.target.value === "" ? null : Number(e.target.value);
            onChange(numValue);
          }}
          onKeyDown={onKeyDown}
          onWheel={(e) => e.currentTarget.blur()}
          autoFocus={autoFocus}
          disabled={disabled}
          className="w-full"
        />
      );

    case ATTRIBUTE_KIND.BOOLEAN:
    case ATTRIBUTE_KIND.CHECKBOX:
      return (
        <Checkbox
          checked={!!value}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
      );

    case ATTRIBUTE_KIND.DATETIME:
      return (
        <DatePicker
          date={value ? new Date(value as string) : null}
          onChange={(newDate: Date) => {
            const newDateValue = newDate ? formatISO(newDate) : null;
            onChange(newDateValue);
          }}
          disabled={disabled}
        />
      );

    case ATTRIBUTE_KIND.DROPDOWN: {
      const items = (attributeSchema.choices ?? []).map((choice) => ({
        value: choice.name,
        label: choice.label ?? choice.name,
        color: choice.color ?? undefined,
        description: choice.description ?? undefined,
      }));

      return (
        <Dropdown
          items={items}
          value={value as string | null}
          onChange={(newValue) => onChange(newValue)}
        />
      );
    }

    case ATTRIBUTE_KIND.TEXTAREA:
      return (
        <MarkdownEditor
          value={(value as string) ?? ""}
          onChange={onChange}
          disabled={disabled}
          className="min-h-[100px] w-full"
        />
      );

    case ATTRIBUTE_KIND.JSON: {
      const jsonValue =
        typeof value === "string" ? value : value !== null ? JSON.stringify(value, null, 2) : "";

      return (
        <JsonEditor
          value={jsonValue}
          onChange={(newValue) => {
            if (!newValue || newValue === "") {
              onChange(null);
              return;
            }
            try {
              const parsed = JSON.parse(newValue);
              onChange(parsed);
            } catch {
              onChange(newValue);
            }
          }}
          disabled={disabled}
        />
      );
    }

    case ATTRIBUTE_KIND.LIST:
      return (
        <List
          value={(value as string[]) ?? []}
          onChange={(newValue) => {
            onChange(newValue.length > 0 ? newValue : null);
          }}
          disabled={disabled}
        />
      );

    case ATTRIBUTE_KIND.COLOR:
      return <ColorPicker value={value} onChange={onChange} disabled={disabled} portal={false}/>;

    case ATTRIBUTE_KIND.PASSWORD:
    case ATTRIBUTE_KIND.HASHED_PASSWORD:
      return (
        <Input
          type="password"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          autoFocus={autoFocus}
          disabled={disabled}
          className="w-full"
        />
      );

    case ATTRIBUTE_KIND.ID:
      return <Input value={(value as string) ?? ""} disabled className="w-full bg-gray-50" />;

    default:
      return (
        <Input
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          autoFocus={autoFocus}
          disabled={disabled}
          className="w-full"
        />
      );
  }
}
