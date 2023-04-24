import { iSchemaKindNameMap } from "../state/atoms/schemaKindName.atom";

type ObjectData = {
  id: string;
  kind: string;
  branch?: string;
}

export const getObjectUrl = (data: ObjectData) => {
  const { kind, id, branch } = data;

  if (branch) {
    return `/objects/${kind.toLocaleLowerCase()}/${id}?branch=${branch}`;
  }

  return `/objects/${kind}/${id}`;
};

const regex = /^Related/; // starts with Related

export const getObjectDetailsUrl = (relationshipsData: {__typename: string}, schemaKindName: iSchemaKindNameMap, relatedNodeId: string) :string => {
  const peerKind: string = relationshipsData?.__typename?.replace(regex, "");
  const peerName = schemaKindName[peerKind];
  const url = `/objects/${peerName}/${relatedNodeId}`;
  return url;
};