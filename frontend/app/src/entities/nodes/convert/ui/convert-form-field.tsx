import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { DynamicField } from "@/shared/components/form/dynamic-form";
import type { DynamicFieldProps } from "@/shared/components/form/type";

import type { ConvertFieldMapping } from "@/entities/nodes/convert/types";
import { ConvertSourceField } from "@/entities/nodes/convert/ui/convert-source-field";
import { getFieldValueFromMapping } from "@/entities/nodes/convert/utils/get-field-value-from-mapping";
import { hasFieldMapping } from "@/entities/nodes/convert/utils/has-field-mapping";
import type { NodeObject } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ConvertFormFieldProps {
  conversionMapping?: ConvertFieldMapping;
  field: DynamicFieldProps;
  sourceObject: NodeObject;
  sourceSchema: ModelSchema;
}

export function ConvertFormField({
  field,
  conversionMapping,
  sourceObject,
  sourceSchema,
}: ConvertFormFieldProps) {
  const [source, setSource] = useState(hasFieldMapping(conversionMapping) ? "source" : "schema");
  const sourceDefaultValue = getFieldValueFromMapping({
    field,
    conversionMapping,
    sourceObject,
  });
  const form = useFormContext();

  const handleSourceChange = (newSource: string) => {
    switch (newSource) {
      case "source":
        form.setValue(field.name, sourceDefaultValue, { shouldValidate: true });
        break;
      case "schema":
        form.setValue(field.name, field.defaultValue, { shouldValidate: true });
        break;
    }

    setSource(newSource);
  };

  return (
    <div className="flex gap-4 px-2 py-4">
      <div className="grow">
        {source === "source" ? (
          <ConvertSourceField
            {...field}
            objectDetailsData={sourceObject}
            sourceSchema={sourceSchema}
            mapping={conversionMapping}
            defaultValue={sourceDefaultValue}
          />
        ) : (
          <DynamicField {...field} />
        )}
      </div>

      <RadioGroup
        orientation="vertical"
        value={source}
        onChange={handleSourceChange}
        className="mt-5 text-sm"
        aria-label="Select source"
      >
        <Radio value="source">From source</Radio>
        <Radio value="schema">Custom value</Radio>
      </RadioGroup>
    </div>
  );
}
