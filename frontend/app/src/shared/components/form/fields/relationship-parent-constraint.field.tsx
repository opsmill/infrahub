import { QSP } from "@/config/qsp";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { RelationshipSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { DynamicRelationshipFieldProps } from "@/shared/components/form/type";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";
import RelationshipField from "./relationship.field";

export interface RelationshipFieldProps extends DynamicRelationshipFieldProps {}

// Select kind (select 2 steps) if needed
const RelationshipParentConstraintField = ({ ...props }: RelationshipFieldProps) => {
  const { objectid, objectKind } = useParams();
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const { schema } = useSchema(objectKind);

  const relationshipSchema = schema?.relationships?.find((relationship) => {
    return relationship.name === qspTab;
  });
  const { schema: peerSchema } = useSchema(relationshipSchema?.peer);

  const peerRelationshipSchema = peerSchema?.relationships.find((relationship) => {
    return relationship.kind === "Parent";
  });

  const { data, isPending } = useGetObject({
    objectId: objectid,
    objectSchema: schema,
    getRelationshipsVisible: (relationships: RelationshipSchema[]): RelationshipSchema[] => {
      return relationships.filter((relationship) => {
        return relationship.name === qspTab;
      });
    },
    relationshipFragment: {
      [peerRelationshipSchema?.name]: {
        node: {
          id: true,
          display_label: true,
          hfid: true,
          __typename: true,
        },
      },
    },
  });

  if (!qspTab) {
    return null;
  }

  if (isPending) {
    return <LoadingIndicator />;
  }

  const currentRelationshipPeers = data?.[qspTab]?.edges;

  if (!currentRelationshipPeers?.length) {
    return <RelationshipField {...props} />;
  }

  const firstRelationshipPeer = currentRelationshipPeers[0].node;

  const defaultParent = firstRelationshipPeer[peerRelationshipSchema?.name]?.node;

  return <RelationshipField {...props} defaultParent={defaultParent} parentDisabled />;
};

export default RelationshipParentConstraintField;
