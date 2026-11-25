import { Skeleton } from "@/shared/components/loading/skeleton";
import { Link } from "@/shared/components/ui/link";
import { sortByOrderWeight } from "@/shared/utils/common";

import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import type {
  NodeAttributeWithMetadata,
  NodeObjectWithMetadata,
} from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { isNodeRelationshipOne } from "@/entities/nodes/object/domain/rules/is-node-relationship-one";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import {
  getIpPoolExtraFields,
  type IpPoolExtraFields,
} from "@/entities/resource-manager/ui/ip-pool/details/get-ip-pool-extra-fields";
import {
  IpPoolField,
  IpPoolFieldList,
  UNSET_FIELD_VALUE,
} from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-field";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";

interface ExtraFieldValuesProps {
  poolId: string;
  schema: ModelSchema;
  fields: IpPoolExtraFields;
}

function ExtraFieldValues({ poolId, schema, fields }: ExtraFieldValuesProps) {
  const { data: pool, isPending } = useGetObject({
    objectSchema: schema,
    objectId: poolId,
    getAttributesVisible: () => fields.attributes,
    getRelationshipsVisible: () => fields.relationships,
  });

  if (isPending) return <Skeleton className="h-10 w-32" />;
  if (!pool) return null;

  const orderedFields = sortByOrderWeight([...fields.attributes, ...fields.relationships]);

  return (
    <IpPoolFieldList>
      {orderedFields.map((field) => (
        <IpPoolField key={field.name} label={field.label || field.name}>
          {isRelationshipSchema(field) ? (
            <RelationshipValue pool={pool} name={field.name} />
          ) : (
            <ObjectAttributeValue
              attributeSchema={field}
              attributeData={pool[field.name] as NodeAttributeWithMetadata}
            />
          )}
        </IpPoolField>
      ))}
    </IpPoolFieldList>
  );
}

interface RelationshipValueProps {
  pool: NodeObjectWithMetadata;
  name: string;
}

function RelationshipValue({ pool, name }: RelationshipValueProps) {
  const relationship = pool[name];
  const peer = isNodeRelationshipOne(relationship) ? relationship.node : null;

  if (!peer) return UNSET_FIELD_VALUE;

  const label = getNodeLabel(peer);

  return (
    <Link
      to={getObjectDetailsUrl(peer.__typename, peer.id)}
      title={label}
      className="text-foreground"
    >
      {label}
    </Link>
  );
}

export interface IpPoolExtraFieldsListProps {
  poolId: string;
  schema: ModelSchema;
}

export function IpPoolExtraFieldsList({ poolId, schema }: IpPoolExtraFieldsListProps) {
  const fields = getIpPoolExtraFields(schema);

  if (fields.attributes.length === 0 && fields.relationships.length === 0) return null;

  return <ExtraFieldValues poolId={poolId} schema={schema} fields={fields} />;
}
