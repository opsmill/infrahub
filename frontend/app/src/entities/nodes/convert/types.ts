import type { EmptyFieldValue, FormFieldValue } from "@/shared/components/form/type";

export interface ConvertFieldMapping {
  is_mandatory: boolean;
  source_field_name: string | null;
  relationship_cardinality: string | null;
}

export type ConvertSource = {
  type: "source";
  name: string;
};

export type ConvertFormFieldValue =
  | {
      source: ConvertSource;
      value: FormFieldValue["value"];
    }
  | EmptyFieldValue;
