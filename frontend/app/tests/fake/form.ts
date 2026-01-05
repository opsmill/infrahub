import type { DynamicFieldProps } from "../../src/shared/components/form/type";

export const buildFormField = (override?: Partial<DynamicFieldProps>): DynamicFieldProps => {
  return {
    name: "field1",
    label: "Field 1",
    defaultValue: null,
    disabled: false,
    type: "Text",
    rules: {
      required: true,
    },
    unique: true,
    ...override,
  } as DynamicFieldProps;
};
