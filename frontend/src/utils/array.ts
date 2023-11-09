export const reduceArrays = (acc: any[], array: any[]) => [...acc, ...array];

export const unifyArray = (array: any[]) => Array.from(new Set(...array));
