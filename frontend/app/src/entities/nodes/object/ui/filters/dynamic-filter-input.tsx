import { Icon } from "@iconify-icon/react";

import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { Button } from "@/shared/components/buttons/button-primitive";
import { JsonEditor } from "@/shared/components/editor/json/json-editor";
import { ColorPicker } from "@/shared/components/inputs/color-picker";
import { DatePicker } from "@/shared/components/inputs/date-picker";
import { Dropdown, type DropdownOption } from "@/shared/components/inputs/dropdown";
import { Enum } from "@/shared/components/inputs/enum";
import { List } from "@/shared/components/list";
import { Badge } from "@/shared/components/ui/badge";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { Input } from "@/shared/components/ui/input";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames, warnUnexpectedType } from "@/shared/utils/common";

import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export interface DynamicFilterInputProps {
  fieldSchema: AttributeSchema | RelationshipSchema;
  value: any;
  onChange: (value: any) => any;
}

export function DynamicFilterInput({ fieldSchema, value, onChange }: DynamicFilterInputProps) {
  if ("peer" in fieldSchema) {
    return (
      <Combobox defaultOpen>
        <PopoverTrigger asChild>
          <div
            className={classNames(
              inputStyle,
              "has-[>:last-child:focus]:border-custom-blue-600 has-[>:last-child:focus]:outline-hidden has-[>:last-child:focus]:ring-2 has-[>:last-child:focus]:ring-custom-blue-600/25",
              "min-w-[132px] max-w-[300px] cursor-pointer"
            )}
          >
            <div className="flex grow flex-wrap gap-2">
              {value?.map(({ id, display_label }) => (
                <Badge key={id} className="flex items-center gap-1 pr-0.5">
                  {display_label}

                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      onChange(value.filter((item) => item.id !== id));
                    }}
                    className="h-4 w-4 text-gray-500 hover:text-gray-800"
                    aria-label="Remove"
                    data-testid="remove-option"
                  >
                    &times;
                  </Button>
                </Badge>
              ))}
            </div>

            <button type="button" className="h-3.5 w-3.5 text-gray-600 outline-hidden">
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </div>
        </PopoverTrigger>

        <ComboboxContent fitTriggerWidth={false}>
          <RelationshipComboboxList
            peer={fieldSchema.peer}
            onSelect={(relationship) => {
              onChange(value ? [...value, relationship] : [relationship]);
            }}
            filterItem={(node) => !value?.some((v) => v.id === node.id)}
          />
        </ComboboxContent>
      </Combobox>
    );
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
