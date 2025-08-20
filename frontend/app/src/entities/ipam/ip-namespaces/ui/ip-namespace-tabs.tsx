import { constructPathForIpam } from "@/entities/ipam/utils";
import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-details/object-details-tab";
import { ModelSchema } from "@/entities/schema/types";

interface IpNamespaceTabsProps {
  objectId: string;
  schema: ModelSchema;
}

export function IpNamespaceTabs({ objectId, schema }: IpNamespaceTabsProps) {
  const relationshipSchemaWithIpPrefix = schema.relationships?.find(
    (rel) => rel.name === "ip_prefixes"
  );
  const relationshipSchemaWithIpAddress = schema.relationships?.find(
    (rel) => rel.name === "ip_addresses"
  );

  return (
    <div className="flex items-stretch gap-2 border-b border-gray-200 w-full text-sm px-2.5">
      {relationshipSchemaWithIpPrefix && (
        <ObjectDetailsTab
          parentKind={schema.kind!}
          parentId={objectId}
          relationship={relationshipSchemaWithIpPrefix}
          href={constructPathForIpam("/ipam")}
        />
      )}

      {relationshipSchemaWithIpAddress && (
        <ObjectDetailsTab
          parentKind={schema.kind!}
          parentId={objectId}
          relationship={relationshipSchemaWithIpAddress}
          href={constructPathForIpam("/ipam/ip_addresses")}
        />
      )}
    </div>
  );
}
