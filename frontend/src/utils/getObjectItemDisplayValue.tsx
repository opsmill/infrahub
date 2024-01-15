import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { Badge } from "../components/display/badge";
import { ColorDisplay } from "../components/display/color-display";
import { DateDisplay } from "../components/display/date-display";
import { PasswordDisplay } from "../components/display/password-display";
import { CodeEditor } from "../components/editor/code-editor";
import { MAX_VALUE_LENGTH_DISPLAY } from "../config/constants";
import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";

export const getObjectItemDisplayValue = (
  row: any,
  attribute: any,
  schemaKindName?: iSchemaKindNameMap
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
    return <pre>{row[attribute?.name]?.value}</pre>;
  }

  if (attribute?.kind === "JSON") {
    return <CodeEditor value={JSON.stringify(row[attribute?.name]?.value)} disabled />;
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

  if (schemaKindName && attribute?.name === "__typename" && row[attribute?.name]) {
    // Use the schema kind name and the value of the __typename to display the type
    return schemaKindName[row[attribute?.name]] ?? "-";
  }

  console.log("attribute: ", attribute);
  console.log("row: ", row);

  const textValue =
    row[attribute?.name]?.label ??
    row[attribute?.name]?.display_label ??
    row[attribute?.name]?.value ??
    row[attribute?.name]?.node?.label ??
    row[attribute?.name]?.node?.display_label ??
    row[attribute?.name]?.node?.value ??
    (typeof row[attribute?.name] === "string" ? row[attribute?.name] : "") ??
    "-";

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
