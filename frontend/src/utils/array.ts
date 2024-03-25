export const reduceArrays = (acc: any[], array: any[]) => [...acc, ...array];

export const unifyArray = (array: any[]) => Array.from(new Set(...array));

export const uniqueItemsArray = (array: any[], key: string) => [
  ...new Map(array.map((item) => [item[key], item])).values(),
];
