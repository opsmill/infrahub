import { getRelationshipParent } from "@/entities/nodes/api/getRelationshipParent";
import { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import useQuery from "@/shared/api/graphql/useQuery";
import { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { FormContext, FormContextType } from "@/shared/components/form/utils/form-context";

import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { gql } from "@apollo/client";
import { use } from "react";
import { GenericRelationshipField } from "./generic-relationship.field";
import { RegularRelationshipField } from "./regular-relationship.field";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
  defaultParent?: Node | null;
}

interface GetDefaultParentParams {
  defaultParent?: Node | null;
  currentParent?: Node | null;
  parentPeer?: string;
  formContext: FormContextType;
}

const convertNodeObjectToNode = (nodeObject: NodeObject | null): Node | null => {
  if (!nodeObject) return null;
  return {
    id: nodeObject.id,
    display_label: nodeObject.display_label || nodeObject.id,
    __typename: nodeObject.__typename,
  };
};

const getDefaultParent = ({
  defaultParent,
  currentParent,
  parentPeer,
  formContext,
}: GetDefaultParentParams): Node | null | undefined => {
  if (currentParent) {
    return currentParent;
  }

  if (parentPeer && isOfKind(parentPeer, formContext.parentSchema as ModelSchema)) {
    return convertNodeObjectToNode(formContext.parentData);
  }

  return defaultParent;
};

// Select kind (select 2 steps) if needed
const RelationshipField = (fieldProps: RelationshipFieldProps) => {
  const { defaultValue, defaultParent, relationship } = fieldProps;

  const formContext = use(FormContext);

  const { isGeneric: isPeerGeneric } = useSchema(relationship.peer);

  const parentRelationship = getParentRelationship(relationship.peer);

  const { schema: parentRelationshipSchema } = useSchema(parentRelationship?.peer);

  const parentRelationshipAttribute = parentRelationshipSchema?.relationships?.find(
    (relationship) => {
      if (parentRelationship?.direction === "bidirectional") {
        return relationship.identifier === parentRelationship?.identifier;
      }

      if (parentRelationship?.direction === "inbound") {
        return (
          relationship.direction === "outbound" &&
          relationship.identifier === parentRelationship?.identifier
        );
      }

      if (parentRelationship?.direction === "outbound") {
        return (
          relationship.direction === "inbound" &&
          relationship.identifier === parentRelationship?.identifier
        );
      }

      return false;
    }
  );

  const id =
    defaultValue?.value && typeof defaultValue.value === "object" && "id" in defaultValue.value
      ? defaultValue.value.id
      : undefined;

  const queryString = getRelationshipParent({
    kind: relationship?.peer,
    attribute: `${parentRelationshipAttribute?.name}__ids`,
    id,
  });

  const query =
    relationship?.peer && parentRelationshipAttribute?.name && id
      ? gql`
          ${queryString}
        `
      : gql`
          query {
            ok
          }
        `;

  const { data } = useQuery(query, { skip: !parentRelationshipSchema?.kind || !id });

  const currentParent = data && relationship.peer && data[relationship.peer]?.edges[0]?.node;

  const computedDefaultParent = getDefaultParent({
    defaultParent,
    currentParent,
    parentPeer: parentRelationship?.peer,
    formContext,
  });

  if (isPeerGeneric) {
    return <GenericRelationshipField {...fieldProps} defaultParent={computedDefaultParent} />;
  }

  return (
    <RegularRelationshipField
      {...fieldProps}
      defaultParent={computedDefaultParent}
      parentRelationship={parentRelationship}
    />
  );
};

export default RelationshipField;
