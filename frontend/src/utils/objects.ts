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