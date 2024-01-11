const regex = /^Related/; // starts with Related

export const getObjectDetailsUrl = (nodeId: string, nodeType: string): string => {
  const peerKind: string = nodeType?.replace(regex, "");

  // if (peerKind === "CoreStandardGroup") {
  //   const url = `/groups/${peerKind}/${nodeId}`;

  //   return url;
  // }

  const url = `/objects/${peerKind}/${nodeId}`;

  return url;
};

export const resolve = (path: string, object: any, separator: string = ".") => {
  const properties: Array<any> = Array.isArray(path) ? path : path.split(separator);

  return properties.reduce((prev: any, curr: any) => prev?.[curr], object);
};
