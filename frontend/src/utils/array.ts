export const reduceArrays = (acc: any[], array: any[]) => [...acc, ...array];

export const unifyArray = (array: any[]) => Array.from(new Set(...array));

export const uniqueItemsArray = (array: any[], key: string) => [
  ...new Map(array.map((item) => [item[key], item])).values(),
];

// Needed for async options to avoid duplicates issues
export const comparedOptions = (a: any, b: any) => a?.id === b?.id;
