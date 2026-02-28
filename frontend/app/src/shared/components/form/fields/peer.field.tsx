import { useMemo } from "react";

import { LabelFormField } from "@/shared/components/form/fields/common";
import type { PoolValue } from "@/shared/components/form/pool-selector";
import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
} from "@/shared/components/form/type";
import { PeerInput } from "@/shared/components/inputs/peer";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";

import { updateRelationshipFieldValue } from "../utils/updateFormFieldValue";

export interface PeerFieldProps extends DynamicRelationshipFieldProps {}

// Select kind (select 2 steps) if needed
const PeerField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  type,
  options,
  parent,
  peer,
  ...props
}: PeerFieldProps) => {
  const { data, isPending } = useGetObject({
    objectId: defaultValue?.value,
    objectSchema: { kind: "CoreNode" },
  });

  const formattedDefaultValue = useMemo(() => {
    return {
      source: defaultValue?.source,
      value: {
        id: defaultValue?.value,
        display_label: data?.display_label,
      },
    };
  }, [data?.id]);

  return (
    <FormField
      key={name}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field }) => {
        const fieldData: FormRelationshipValue = field.value;

        const onChange = (newValue: Node | PoolValue | null) => {
          field.onChange(updateRelationshipFieldValue(newValue, formattedDefaultValue));
        };

        const value =
          fieldData?.value && !Array.isArray(fieldData.value)
            ? ({
                ...fieldData.value,
                display_label: fieldData.value?.display_label ?? data?.display_label,
              } as Node)
            : null;

        return (
          <div className="relative flex flex-col space-y-2">
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />

            <div className="flex gap-2">
              <FormInput>
                <PeerInput
                  {...field}
                  {...props}
                  value={value}
                  onChange={onChange}
                  peer={peer}
                  disabled={isPending || props.disabled}
                />
              </FormInput>
            </div>
            <FormMessage />
          </div>
        );
      }}
    />
  );
};

export default PeerField;
