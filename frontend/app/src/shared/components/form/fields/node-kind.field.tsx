import { useAtomValue } from "jotai";
import { useState } from "react";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { canDisplayResetActions } from "@/shared/components/form/utils/canDisplayResetActions";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { Badge } from "../../ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "../../ui/combobox";
import { FormField, FormInput, FormMessage } from "../../ui/form";
import type { FormAttributeValue, FormFieldProps } from "../type";
import { updateFormFieldValue } from "../utils/updateFormFieldValue";
import { LabelFormField, ResetAction } from "./common";

export function NodeKindField({
  defaultValue = DEFAULT_FORM_FIELD_VALUE,
  deprecation,
  isBulkUpdate,
  attribute,
  label,
  description,
  rules,
  ...props
}: FormFieldProps) {
  const nodes = useAtomValue(nodeSchemasAtom);

  return (
    <FormField
      render={({ field }) => {
        const [open, setOpen] = useState(false);

        const fieldData: FormAttributeValue = field.value;
        const currentValue = (fieldData?.value as string | undefined) ?? null;
        const currentNode = nodes.find((node) => {
          return node.kind === currentValue;
        });

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField label={label} deprecation={deprecation} description={description} required={rules.required} />

            <Combobox open={open} onOpenChange={setOpen}>
              <FormInput>
                <ComboboxTrigger>
                  {currentNode && (
                    <div className="flex w-full justify-between">
                      {currentNode?.label} <Badge>{currentNode?.namespace}</Badge>
                    </div>
                  )}
                </ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList>
                  {nodes.map((node) => {
                    return (
                      <ComboboxItem
                        key={node.id}
                        selectedValue={currentValue}
                        value={node.kind!}
                        keywords={[node.label as string]}
                        onSelect={() => {
                          const newValue = node.kind === currentValue ? null : node.kind;
                          field.onChange(updateFormFieldValue(newValue ?? null, defaultValue));

                          setOpen(false);
                        }}
                      >
                        <div className="flex w-full justify-between">
                          {node.label} <Badge>{node.namespace}</Badge>
                        </div>
                      </ComboboxItem>
                    );
                  })}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>

            {!props.disabled && canDisplayResetActions(attribute, isBulkUpdate) && (
              <ResetAction field={field} defaultValue={defaultValue} />
            )}

            <FormMessage />
          </div>
        );
      }}
      {...props}
    />
  );
}
