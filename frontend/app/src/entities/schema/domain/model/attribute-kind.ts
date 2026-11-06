import type { AttributeKind } from "@/entities/schema/domain/model/schema";

export const ATTRIBUTE_KIND = {
  ID: "ID",
  DROPDOWN: "Dropdown",
  TEXT: "Text",
  TEXTAREA: "TextArea",
  DATETIME: "DateTime",
  EMAIL: "Email",
  PASSWORD: "Password",
  HASHED_PASSWORD: "HashedPassword",
  URL: "URL",
  FILE: "File",
  MAC_ADDRESS: "MacAddress",
  COLOR: "Color",
  NUMBER: "Number",
  BANDWIDTH: "Bandwidth",
  IP_HOST: "IPHost",
  IP_NETWORK: "IPNetwork",
  IP_ADDRESS: "IPAddress",
  CHECKBOX: "Checkbox",
  LIST: "List",
  JSON: "JSON",
  ANY: "Any",
  BOOLEAN: "Boolean",
  NODE_KIND: "NodeKind",
} as const;

// Reference: https://docs.infrahub.app/schema/nodes-and-attributes > Attribute kinds behavior in the UI
export const ATTRIBUTE_KINDS_FOR_LIST_VIEW: readonly AttributeKind[] = [
  ATTRIBUTE_KIND.TEXT,
  ATTRIBUTE_KIND.NUMBER,
  ATTRIBUTE_KIND.BOOLEAN,
  ATTRIBUTE_KIND.DROPDOWN,
  ATTRIBUTE_KIND.EMAIL,
  ATTRIBUTE_KIND.URL,
  ATTRIBUTE_KIND.FILE,
  ATTRIBUTE_KIND.MAC_ADDRESS,
  ATTRIBUTE_KIND.COLOR,
  ATTRIBUTE_KIND.BANDWIDTH,
  ATTRIBUTE_KIND.IP_HOST,
  ATTRIBUTE_KIND.IP_NETWORK,
  ATTRIBUTE_KIND.IP_ADDRESS,
  ATTRIBUTE_KIND.DATETIME,
];

/** Kinds the column picker can turn on, though they are not shown by default. */
export const ATTRIBUTE_KINDS_REVEALABLE_IN_LIST_VIEW: readonly AttributeKind[] = [
  ...ATTRIBUTE_KINDS_FOR_LIST_VIEW,
  ATTRIBUTE_KIND.LIST,
  ATTRIBUTE_KIND.JSON,
  ATTRIBUTE_KIND.ANY,
  ATTRIBUTE_KIND.PASSWORD,
  ATTRIBUTE_KIND.HASHED_PASSWORD,
];
