import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";

const regex = /^Related/; // starts with Related

export const getObjectDetailsUrl = (
  nodeId: string,
  nodeType: string,
  schemaKindName: iSchemaKindNameMap
): string => {
  const peerKind: string = nodeType?.replace(regex, "");

  const peerName = schemaKindName[peerKind];

  const url = `/objects/${peerName}/${nodeId}`;

  return url;
};

export const resolve = (path: string, object: any, separator: string = ".") => {
  const properties: Array<any> = Array.isArray(path) ? path : path.split(separator);

  return properties.reduce((prev: any, curr: any) => prev?.[curr], object);
};
