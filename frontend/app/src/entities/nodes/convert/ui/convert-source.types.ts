import type React from "react";

import type {
  ConvertFieldMapping,
  ConvertFormFieldValue,
} from "@/entities/nodes/convert/domain/model/convert";
import type { NodeCore, NodeObject } from "@/entities/nodes/object/domain/model/node";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface ConvertSourceInputProps {
  sourceObject: NodeObject;
  sourceSchema: ModelSchema;
  mapping?: ConvertFieldMapping;
  className?: string;
  value: ConvertFormFieldValue;
  onChange: (value: ConvertFormFieldValue) => void;
}

export interface ConvertSourceRelationshipInputProps extends ConvertSourceInputProps {
  peer: string;
}

export interface ConvertSourceOption {
  source: {
    type: "source";
    name: string;
    label: string | null | undefined;
  };
  isDefaultMatch: boolean;
}

export interface AttributeSourceOption extends ConvertSourceOption {
  value: string | string[] | number | boolean | null;
  label: React.ReactNode;
}

export interface RelationshipOneSourceOption extends ConvertSourceOption {
  value: NodeCore | null;
}

export interface RelationshipManySourceOption extends ConvertSourceOption {
  value: Array<NodeCore> | null;
}
