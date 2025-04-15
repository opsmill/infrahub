import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useAtomValue } from "jotai";
import { useState } from "react";
import { Badge } from "../../ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "../../ui/combobox";
import { FormField, FormInput, FormMessage } from "../../ui/form";
import { DEFAULT_FORM_FIELD_VALUE } from "../constants";
import { updateFormFieldValue } from "../utils/updateFormFieldValue";
import { LabelFormField } from "./common";

export function NdoeKindSelect({ label, defaultValue, description, ...props }) {
  const nodes = useAtomValue(nodeSchemasAtom);

  return (
    <FormField
      render={({ field }) => {
        const [open, setOpen] = useState(false);

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label={label}
              description={description}
              required={props.rules.required}
            />

            <Combobox open={open} onOpenChange={setOpen}>
              <FormInput>
                <ComboboxTrigger>
                  {defaultValue.value && (
                    <div className="w-full flex justify-between">
                      {defaultValue.value.label} <Badge>{defaultValue.value.namespace}</Badge>
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
                        selectedValue={defaultValue?.kind}
                        value={node.kind!}
                        keywords={[node.label as string]}
                        onSelect={() => {
                          const newValue = node.kind === defaultValue?.kind ? null : node.kind;
                          field.onChange(
                            updateFormFieldValue(newValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                          );

                          setOpen(false);
                        }}
                      >
                        <div className="w-full flex justify-between">
                          {node.label} <Badge>{node.namespace}</Badge>
                        </div>
                      </ComboboxItem>
                    );
                  })}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>

            <FormMessage />
          </div>
        );
      }}
      {...props}
    />
  );
}
