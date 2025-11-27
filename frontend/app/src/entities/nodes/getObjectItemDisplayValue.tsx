import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";

import { MAX_VALUE_LENGTH_DISPLAY } from "@/config/constants";

import type {
  AnyAttribute,
  CheckboxAttribute,
  Dropdown,
  IpHost,
  IpNetwork,
  JsonAttribute,
  ListAttribute,
  Maybe,
  NumberAttribute,
  RelationshipProperty,
  TextAttribute,
} from "@/shared/api/graphql/generated/graphql";
import { Badge } from "@/shared/components/display/badge";
import { ColorDisplay } from "@/shared/components/display/color-display";
import { DateDisplay } from "@/shared/components/display/date-display";
import { PasswordDisplay } from "@/shared/components/display/password-display";
import { TextDisplay } from "@/shared/components/display/text-display";
import { CodeViewer } from "@/shared/components/editor/code/code-viewer";
import { MarkdownRender } from "@/shared/components/editor/markdown/markdown-render";
import { Link } from "@/shared/components/ui/link";

import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import type { iSchemaKindNameMap } from "@/entities/schema/stores/schemaKindName.atom";
import type { AttributeKind, AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

const getTextValue = (data: any) => {
  // If data.node is a node object, use getNodeLabel
  if (data?.node && "__typename" in data.node && "id" in data.node) {
    return data?.label ?? getNodeLabel(data.node) ?? data?.value ?? "-";
  }

  return (
    data?.label ??
    data?.display_label ??
    data?.value ??
    data?.node?.label ??
    data?.node?.display_label ??
    data?.node?.value ??
    "-"
  );
};

export const getDisplayValue = (
  row: any,
  attribute: any,
  schemaKindName?: iSchemaKindNameMap,
  schemaKindLabel?: iSchemaKindNameMap
) => {
  if (!row) {
    return;
  }

  if (row[attribute?.name]?.value === false) {
    return <XMarkIcon className="h-4 w-4" />;
  }

  if (row[attribute?.name]?.value === true) {
    return <CheckIcon className="h-4 w-4" />;
  }

  if (attribute?.kind === "TextArea") {
    return <MarkdownRender markdownText={row[attribute?.name]?.value} />;
  }

  if (attribute?.kind === "JSON") {
    return <CodeViewer>{JSON.stringify(row[attribute?.name]?.value ?? "", null, 2)}</CodeViewer>;
  }

  if (attribute?.kind === "List") {
    const items = row[attribute?.name]?.value?.map((value?: string) => value ?? "-").slice(0, 5);

    const rest = row[attribute?.name]?.value?.slice(5)?.length;

    return (
      <div className="flex flex-wrap items-center">
        {items?.map((item: string, index: number) => (
          <Badge key={index}>{item}</Badge>
        ))}

        {items?.length !== row[attribute?.name]?.value?.length && <i>{`(${rest} more)`}</i>}
      </div>
    );
  }

  if (row[attribute?.name]?.edges) {
    const items = row[attribute?.name]?.edges
      .map((edge: any) => (edge?.node ? getNodeLabel(edge.node) : (edge?.node?.value ?? "-")))
      .slice(0, 5);

    const rest = row[attribute?.name]?.edges?.slice(5)?.length;

    return (
      <div className="flex flex-wrap items-center">
        {items.map((item: string, index: number) => (
          <Badge key={index}>{item}</Badge>
        ))}

        {items.length !== row[attribute?.name]?.edges?.length && <i>{`(${rest} more)`}</i>}
      </div>
    );
  }

  if (attribute?.kind === "DateTime" && row[attribute?.name]?.value) {
    return <DateDisplay date={row[attribute?.name]?.value} />;
  }

  const textValue = getTextValue(row[attribute?.name]);

  if (schemaKindLabel && attribute?.name === "__typename" && row[attribute?.name]) {
    // Use the schema kind name and the value of the __typename to display the type, or use the value itself if not defined
    return schemaKindLabel[row[attribute?.name]] ?? textValue;
  }

  if (schemaKindName && attribute?.name === "__typename" && row[attribute?.name]) {
    // Use the schema kind name and the value of the __typename to display the type, or use the value itself if not defined
    return schemaKindName[row[attribute?.name]] ?? textValue;
  }

  if (attribute?.kind === "Password") {
    return <PasswordDisplay value={textValue} />;
  }

  if (textValue?.length > MAX_VALUE_LENGTH_DISPLAY) {
    return `${textValue.substr(0, MAX_VALUE_LENGTH_DISPLAY)} ...`;
  }

  if (attribute?.kind === "Color" && row[attribute?.name]?.value) {
    return <ColorDisplay color={row[attribute?.name]?.value} />;
  }

  if (row[attribute?.name]?.color) {
    return <ColorDisplay value={textValue} color={row[attribute?.name]?.color} />;
  }

  return textValue;
};

export type FieldSchema = AttributeSchema | RelationshipSchema;

export type AttributeType =
  | TextAttribute
  | NumberAttribute
  | CheckboxAttribute
  | Dropdown
  | IpHost
  | IpNetwork
  | JsonAttribute
  | ListAttribute
  | AnyAttribute;

export type Node = {
  id: string;
  display_label: string;
  badge?: string;
  __typename: string;
};

export type RelationshipOneType = {
  node: Node | null;
  properties?: Maybe<RelationshipProperty> & { source?: { __typename?: string } | null };
};

export type RelationshipManyType = {
  count?: number;
  edges: Array<RelationshipOneType>;
};

export type RelationshipType = RelationshipManyType | RelationshipOneType;

export const ObjectAttributeValue = ({
  attributeSchema,
  attributeValue,
}: {
  attributeSchema: FieldSchema;
  attributeValue: AttributeType;
}) => {
  if (!attributeValue.value && attributeValue.value !== 0 && attributeValue.value !== false) {
    return "-";
  }

  switch (attributeSchema.kind as AttributeKind) {
    case ATTRIBUTE_KIND.ID:
    case ATTRIBUTE_KIND.TEXT:
    case ATTRIBUTE_KIND.NUMBER:
    case ATTRIBUTE_KIND.BANDWIDTH:
    case ATTRIBUTE_KIND.EMAIL:
    case ATTRIBUTE_KIND.MAC_ADDRESS:
    case ATTRIBUTE_KIND.FILE:
    case ATTRIBUTE_KIND.IP_HOST:
    case ATTRIBUTE_KIND.IP_NETWORK:
    case ATTRIBUTE_KIND.ANY:
      return <TextDisplay>{getTextValue(attributeValue).toString()}</TextDisplay>;
    case ATTRIBUTE_KIND.URL:
      return (
        <Link to={getTextValue(attributeValue).toString()} target="_blank" rel="noreferrer">
          {getTextValue(attributeValue).toString()}
        </Link>
      );
    case ATTRIBUTE_KIND.BOOLEAN:
    case ATTRIBUTE_KIND.CHECKBOX:
      return attributeValue.value ? (
        <CheckIcon className="size-4" />
      ) : (
        <XMarkIcon className="size-4" />
      );
    case ATTRIBUTE_KIND.DATETIME:
      return <DateDisplay date={getTextValue(attributeValue)} />;
    case ATTRIBUTE_KIND.TEXTAREA:
      return <MarkdownRender markdownText={getTextValue(attributeValue)} />;
    case ATTRIBUTE_KIND.PASSWORD:
    case ATTRIBUTE_KIND.HASHED_PASSWORD:
      return <PasswordDisplay value={getTextValue(attributeValue)} />;
    case ATTRIBUTE_KIND.DROPDOWN: {
      const dropdownAttribute = attributeValue as Dropdown;
      return (
        <ColorDisplay value={getTextValue(dropdownAttribute)} color={dropdownAttribute.color} />
      );
    }
    case ATTRIBUTE_KIND.COLOR:
      return <ColorDisplay color={attributeValue.value} />;
    case ATTRIBUTE_KIND.LIST: {
      const items = attributeValue.value?.map((value?: string) => value ?? "-").slice(0, 5);

      const rest = attributeValue.value.slice(5).length;

      return (
        <div className="flex flex-wrap items-center">
          {items?.map((item: string, index: number) => (
            <Badge key={index}>{item}</Badge>
          ))}

          {items?.length !== attributeValue.value?.length && <i>{`(${rest} more)`}</i>}
        </div>
      );
    }
    case ATTRIBUTE_KIND.JSON:
      return <CodeViewer>{JSON.stringify(attributeValue.value ?? "", null, 2)}</CodeViewer>;
    default:
      return (
        <div className="flex min-h-7 min-w-7 items-center">{getTextValue(attributeValue)}</div>
      );
  }
};
