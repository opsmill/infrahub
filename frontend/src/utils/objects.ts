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

export const resolve = (path: string, object: any, separator: string = ".") => {
  const properties: Array<any> = Array.isArray(path) ? path : path.split(separator);

  return properties.reduce((prev: any, curr: any) => prev?.[curr], object);
};