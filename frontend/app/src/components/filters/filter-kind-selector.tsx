import { DEFAULT_FORM_FIELD_VALUE } from "@/components/form/constants";
import { LabelFormField } from "@/components/form/fields/common";
import { updateFormFieldValue } from "@/components/form/utils/updateFormFieldValue";
import { Badge } from "@/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/components/ui/form";
import useFilters from "@/hooks/useFilters";
import { iGenericSchema, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";
import { useState } from "react";

export const FilterKindSelector = ({ genericSchema }: { genericSchema: iGenericSchema }) => {
  const [activeFilters] = useFilters();
  const availableNodes = useAtomValue(schemaState);
  const availableProfiles = useAtomValue(profilesAtom);
  const allAvailableSchemas = [...availableNodes, ...availableProfiles];

  const selectedKindFilter = activeFilters.find((filter) => filter.name == "kind__value");
  const compatibleSchemas = (genericSchema.used_by ?? [])
    .map((kindValue) => {
      if (!allAvailableSchemas) return null;

      return allAvailableSchemas.find((schema) => schema.kind === kindValue);
    })
    .filter((schema) => !!schema);

  return (
    <FormField
      name="kind"
      defaultValue={
        selectedKindFilter
          ? { source: { type: "user" }, value: selectedKindFilter.value }
          : DEFAULT_FORM_FIELD_VALUE
      }
      render={({ field }) => {
        const [isDropdownOpen, setIsDropdownOpen] = useState(false);
        const currentFieldValue = field.value;
        const selectedSchema = allAvailableSchemas.find(
          (schema) => schema.kind === currentFieldValue?.value
        );

        return (
          <div className="flex flex-col gap-2">
            <LabelFormField
              label="Kind"
              description="Select a kind to filter nodes"
              fieldData={currentFieldValue}
            />

            <Combobox open={isDropdownOpen} onOpenChange={setIsDropdownOpen}>
              <FormInput>
                <ComboboxTrigger>
                  {selectedSchema && (
                    <div className="w-full flex justify-between">
                      {selectedSchema.label} <Badge>{selectedSchema.namespace}</Badge>
                    </div>
                  )}
                </ComboboxTrigger>
              </FormInput>

              <ComboboxContent>
                <ComboboxList>
                  {compatibleSchemas.map((schemaOption) => (
                    <ComboboxItem
                      key={schemaOption.kind}
                      selectedValue={selectedSchema?.kind}
                      value={schemaOption.kind!}
                      onSelect={() => {
                        const newSelectedValue =
                          schemaOption.kind === selectedSchema?.kind ? null : schemaOption.kind;
                        field.onChange(
                          updateFormFieldValue(newSelectedValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                        );
                        setIsDropdownOpen(false);
                      }}
                    >
                      {schemaOption.label}{" "}
                      <Badge className="ml-auto">{schemaOption?.namespace}</Badge>
                    </ComboboxItem>
                  ))}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>

            <FormMessage />
          </div>
        );
      }}
    />
  );
};
