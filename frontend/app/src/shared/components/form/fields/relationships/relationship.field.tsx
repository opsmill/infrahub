import { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { DynamicRelationshipFieldProps } from "@/shared/components/form/type";

import { GenericRelationshipField } from "./generic-relationship.field";
import { NodeRelationshipField } from "./regular-relationship.field";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
  defaultParent?: Node | null;
}

// Select kind (select 2 steps) if needed
const RelationshipField = (fieldProps: RelationshipFieldProps) => {
  const { relationship } = fieldProps;

  const { isGeneric: isPeerGeneric } = useSchema(relationship.peer);

  if (isPeerGeneric) {
    return <GenericRelationshipField {...fieldProps} />;
  }

  return <NodeRelationshipField {...fieldProps} />;
};

export default RelationshipField;
