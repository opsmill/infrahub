import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { JsonEditor } from "@/shared/components/editor/json/json-editor";
import { ColorPicker } from "@/shared/components/inputs/color-picker";
import { DatePicker } from "@/shared/components/inputs/date-picker";
import { Dropdown, type DropdownOption } from "@/shared/components/inputs/dropdown";
import { Enum } from "@/shared/components/inputs/enum";
import { List } from "@/shared/components/inputs/list";
import { Input } from "@/shared/components/ui/input";
import { warnUnexpectedType } from "@/shared/utils/common";

import { RelationshipFilterCombobox } from "@/entities/nodes/object/ui/filters/relationship-filter-combobox";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface DynamicFilterInputProps {
  fieldSchema: AttributeSchema | RelationshipSchema;
  value: any;
  onChange: (value: any) => any;
}

export function DynamicFilterInput({ fieldSchema, value, onChange }: DynamicFilterInputProps) {
  if ("peer" in fieldSchema) {
    return <RelationshipFilterCombobox peer={fieldSchema.peer} value={value} onChange={onChange} />;
  }

  const fieldKind = fieldSchema.kind as AttributeKind;
  switch (fieldKind) {
    case ATTRIBUTE_KIND.TEXT: {
      if (fieldSchema.enum) {
        return (
          <Enum
            items={fieldSchema.enum as string[]}
            value={value}
            onChange={onChange}
            defaultOpen={true}
            fitTriggerWidth={false}
            className="min-w-[132px]"
          />
        );
      }
      return <Input autoFocus value={value} onChange={onChange} />;
    }
    case ATTRIBUTE_KIND.ID:
    case ATTRIBUTE_KIND.TEXTAREA:
    case ATTRIBUTE_KIND.EMAIL:
    case ATTRIBUTE_KIND.FILE:
    case ATTRIBUTE_KIND.MAC_ADDRESS:
    case ATTRIBUTE_KIND.IP_HOST:
    case ATTRIBUTE_KIND.IP_NETWORK:
    case ATTRIBUTE_KIND.PASSWORD:
    case ATTRIBUTE_KIND.HASHED_PASSWORD:
    case ATTRIBUTE_KIND.URL:
    case ATTRIBUTE_KIND.ANY: {
      return <Input autoFocus value={value} onChange={onChange} />;
    }
    case ATTRIBUTE_KIND.BANDWIDTH:
    case ATTRIBUTE_KIND.NUMBER: {
      return (
        <Input
          type="number"
          autoFocus
          value={value}
          onChange={(e) => onChange(e.target.valueAsNumber)}
        />
      );
    }
    case ATTRIBUTE_KIND.DROPDOWN: {
      return (
        <Dropdown
          items={
            (fieldSchema.choices?.map((choice) => {
              return {
                ...choice,
                value: choice.name,
              };
            }) ?? []) as DropdownOption[]
          }
          value={value ?? null}
          onChange={onChange}
          defaultOpen
          className="min-w-[132px]"
        />
      );
    }
    case ATTRIBUTE_KIND.COLOR: {
      return <ColorPicker value={value} onChange={onChange} />;
    }
    case ATTRIBUTE_KIND.BOOLEAN:
    case ATTRIBUTE_KIND.CHECKBOX: {
      return (
        <RadioGroup
          value={value?.toString()}
          onChange={(newValue) => {
            if (newValue === "true") return onChange(true);
            if (newValue === "false") return onChange(false);
            return onChange(newValue);
          }}
          className="rounded-md border border-gray-300 p-2"
        >
          <Radio value="true">True</Radio>
          <Radio value="false">False</Radio>
        </RadioGroup>
      );
    }
    case ATTRIBUTE_KIND.LIST: {
      return <List value={value} onChange={onChange} />;
    }
    case ATTRIBUTE_KIND.DATETIME: {
      return <DatePicker date={value ? new Date(value) : null} onChange={onChange} />;
    }
    case ATTRIBUTE_KIND.JSON: {
      return <JsonEditor value={value} onChange={onChange} />;
    }
    default: {
      warnUnexpectedType(fieldKind);
      return null;
    }
  }
}
