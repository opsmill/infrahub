import { Icon } from "@/shared/components/display/icon";

import type {
  AttributeKind,
  AttributeSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { isRelationshipSchema } from "@/entities/schema/domain/rules/is-relationship-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const ATTRIBUTE_ICONS: Record<AttributeKind, string> = {
  Text: "mdi:text",
  TextArea: "mdi:text-box-outline",
  Number: "mdi:numeric",
  Boolean: "mdi:checkbox-marked-circle-outline",
  Dropdown: "mdi:format-list-bulleted-square",
  DateTime: "mdi:calendar-clock",
  Email: "mdi:at",
  Password: "mdi:key-outline",
  HashedPassword: "mdi:key-outline",
  URL: "mdi:web",
  File: "mdi:file-outline",
  MacAddress: "mdi:memory",
  Color: "mdi:palette-outline",
  Bandwidth: "mdi:gauge",
  IPHost: "mdi:ip-network-outline",
  IPNetwork: "mdi:ip-network-outline",
  IPAddress: "mdi:ip-outline",
  Checkbox: "mdi:checkbox-marked-circle-outline",
  List: "mdi:format-list-bulleted-square",
  JSON: "mdi:code-json",
  Any: "mdi:alert-circle-outline",
  ID: "mdi:card-account-details-outline",
  NodeKind: "mdi:code-json",
} as const;

interface FieldSchemaIconProps {
  fieldSchema: AttributeSchema | RelationshipSchema;
}

export function FieldSchemaIcon({ fieldSchema }: FieldSchemaIconProps) {
  if (isRelationshipSchema(fieldSchema)) {
    return <RelationshipFieldIcon relationshipSchema={fieldSchema} />;
  }

  return <AttributeFieldIcon attributeKind={fieldSchema.kind as AttributeKind} />;
}

function AttributeFieldIcon({ attributeKind }: { attributeKind: AttributeKind }) {
  const icon = ATTRIBUTE_ICONS[attributeKind];
  if (!icon) return null;

  return <Icon icon={icon} />;
}

function RelationshipFieldIcon({ relationshipSchema }: { relationshipSchema: RelationshipSchema }) {
  const { schema } = useSchema(relationshipSchema.peer);

  return <Icon icon={getSchemaIcon(schema)} />;
}
