export const uniqueItemsArray = (array: any[], key: string) => [
  ...new Map(array.map((item) => [item[key], item])).values(),
];

// Needed for async options to avoid duplicates issues
export const comparedOptions = (a: any, b: any) => a?.id === b?.id;

export const areObjectArraysEqualById = (
  arr1: Array<{ id: string }>,
  arr2: Array<{ id: string }>
): boolean => {
  if (arr1.length !== arr2.length) return false;

  const idSet = new Set(arr1.map((item) => item.id));
  return idSet.size === arr1.length && arr2.every((item) => idSet.has(item.id));
};
