import { Skeleton } from "@/shared/components/loading/skeleton";
import { Link } from "@/shared/components/ui/link";

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
} from "@/entities/resource-manager/domain/rules/get-ip-pool-extra-fields";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface ExtraFieldProps {
  label: string;
  children: React.ReactNode;
}

function ExtraField({ label, children }: ExtraFieldProps) {
  return (
    <div className="flex min-w-0 items-baseline gap-1.5">
      <dt className="shrink-0 text-foreground-muted">{label}</dt>
      <dd className="min-w-0 truncate text-foreground">{children}</dd>
    </div>
  );
}

interface ExtraFieldsListProps {
  poolId: string;
  schema: ModelSchema;
  fields: IpPoolExtraFields;
}

function ExtraFieldsList({ poolId, schema, fields }: ExtraFieldsListProps) {
  const { data: pool, isPending } = useGetObject({
    objectSchema: schema,
    objectId: poolId,
    getAttributesVisible: () => fields.attributes,
    getRelationshipsVisible: () => fields.relationships,
  });

  if (isPending) return <Skeleton className="mt-2 h-5 w-64" />;

  // the extra fields add context, so a failed read leaves the header as it is
  if (!pool) return null;

  return (
    <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {fields.attributes.map((attribute) => (
        <ExtraField key={attribute.name} label={attribute.label || attribute.name}>
          <ObjectAttributeValue
            attributeSchema={attribute}
            attributeData={pool[attribute.name] as NodeAttributeWithMetadata}
          />
        </ExtraField>
      ))}
      {fields.relationships.map((relationship) => (
        <ExtraField key={relationship.name} label={relationship.label || relationship.name}>
          <RelationshipValue pool={pool} name={relationship.name} />
        </ExtraField>
      ))}
    </dl>
  );
}

interface RelationshipValueProps {
  pool: NodeObjectWithMetadata;
  name: string;
}

function RelationshipValue({ pool, name }: RelationshipValueProps) {
  const relationship = pool[name];
  const peer = isNodeRelationshipOne(relationship) ? relationship.node : null;

  if (!peer) return "-";

  return (
    <Link to={getObjectDetailsUrl(peer.__typename, peer.id)} className="font-medium">
      {getNodeLabel(peer)}
    </Link>
  );
}

export interface IpPoolExtraFieldsLineProps {
  poolId: string;
  schema: ModelSchema;
}

export function IpPoolExtraFieldsLine({ poolId, schema }: IpPoolExtraFieldsLineProps) {
  const fields = getIpPoolExtraFields(schema);

  if (fields.attributes.length === 0 && fields.relationships.length === 0) return null;

  return <ExtraFieldsList poolId={poolId} schema={schema} fields={fields} />;
}
