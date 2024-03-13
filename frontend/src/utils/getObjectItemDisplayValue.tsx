import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { Badge } from "../components/display/badge";
import { ColorDisplay } from "../components/display/color-display";
import { DateDisplay } from "../components/display/date-display";
import { PasswordDisplay } from "../components/display/password-display";
import { CodeEditor } from "../components/editor/code-editor";
import { MAX_VALUE_LENGTH_DISPLAY, SCHEMA_ATTRIBUTE_KIND } from "../config/constants";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";
import { MarkdownViewer } from "../components/editor/markdown-viewer";
import { TextDisplay } from "../components/display/text-display";
import { components } from "../infraops";
import {
  AnyAttribute,
  CheckboxAttribute,
  Dropdown,
  IpHost,
  IpNetwork,
  JsonAttribute,
  ListAttribute,
  NumberAttribute,
  TextAttribute,
} from "../generated/graphql";
import { SchemaAttributeType } from "../screens/edit-form-hook/dynamic-control-types";

const getTextValue = (data: any) => {
  if (typeof data === "string" || typeof data === "number") {
    return data;
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
    return <MarkdownViewer markdownText={row[attribute?.name]?.value} />;
  }

  if (attribute?.kind === "JSON") {
    return (
      <CodeEditor value={JSON.stringify(row[attribute?.name]?.value ?? "", null, 2)} disabled />
    );
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
      .map((edge: any) => edge?.node?.display_label ?? edge?.node?.value ?? "-")
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

export const getObjectItemDisplayValue = (
  row: any,
  attribute: any,
  schemaKindName?: iSchemaKindNameMap,
  schemaKindLabel?: iSchemaKindNameMap
) => {
  return (
    <div className="flex items-center min-w-7 min-h-7">
      {getDisplayValue(row, attribute, schemaKindName, schemaKindLabel)}
    </div>
  );
};

export const ObjectAttributeValue = ({
  attributeSchema,
  attributeValue,
}: {
  attributeSchema: components["schemas"]["AttributeSchema"];
  attributeValue:
    | TextAttribute
    | NumberAttribute
    | CheckboxAttribute
    | Dropdown
    | IpHost
    | IpNetwork
    | JsonAttribute
    | ListAttribute
    | AnyAttribute;
}) => {
  if (!attributeValue.value) return null;

  switch (attributeSchema.kind as SchemaAttributeType) {
    case SCHEMA_ATTRIBUTE_KIND.ID:
    case SCHEMA_ATTRIBUTE_KIND.TEXT:
    case SCHEMA_ATTRIBUTE_KIND.NUMBER:
    case SCHEMA_ATTRIBUTE_KIND.BANDWIDTH:
    case SCHEMA_ATTRIBUTE_KIND.EMAIL:
    case SCHEMA_ATTRIBUTE_KIND.URL:
    case SCHEMA_ATTRIBUTE_KIND.MAC_ADDRESS:
    case SCHEMA_ATTRIBUTE_KIND.FILE:
    case SCHEMA_ATTRIBUTE_KIND.IP_HOST:
    case SCHEMA_ATTRIBUTE_KIND.IP_NETWORK:
    case SCHEMA_ATTRIBUTE_KIND.ANY:
      return <TextDisplay>{getTextValue(attributeValue).toString()}</TextDisplay>;
    case SCHEMA_ATTRIBUTE_KIND.BOOLEAN:
    case SCHEMA_ATTRIBUTE_KIND.CHECKBOX:
      return attributeValue ? <CheckIcon className="h-4 w-4" /> : <XMarkIcon className="h-4 w-4" />;
    case SCHEMA_ATTRIBUTE_KIND.DATETIME:
      return <DateDisplay date={getTextValue(attributeValue)} />;
    case SCHEMA_ATTRIBUTE_KIND.TEXTAREA:
      return <MarkdownViewer markdownText={getTextValue(attributeValue)} />;
    case SCHEMA_ATTRIBUTE_KIND.PASSWORD:
    case SCHEMA_ATTRIBUTE_KIND.HASHED_PASSWORD:
      return <PasswordDisplay value={getTextValue(attributeValue)} />;
    case SCHEMA_ATTRIBUTE_KIND.DROPDOWN:
      const dropdownAttribute = attributeValue as Dropdown;
      return (
        <ColorDisplay value={getTextValue(dropdownAttribute)} color={dropdownAttribute.color} />
      );
    case SCHEMA_ATTRIBUTE_KIND.COLOR:
      return <ColorDisplay color={attributeValue.value} />;
    case SCHEMA_ATTRIBUTE_KIND.LIST:
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
    case SCHEMA_ATTRIBUTE_KIND.JSON:
      return <CodeEditor value={JSON.stringify(attributeValue.value ?? "", null, 2)} disabled />;
    default:
      return (
        <div className="flex items-center min-w-7 min-h-7">{getTextValue(attributeValue)}</div>
      );
  }
};
