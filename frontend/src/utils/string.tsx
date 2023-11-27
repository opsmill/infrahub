/**
 * Same as JSON.stringify, but this will remove the quotes around keys/properties from the output
 *
 * const data = {a: 1, b: [{tags: ["Tag A"]}, {tags: ["Tag B"]}]}
 *
 * JSON.stringify(data)
 * '{"a":1,"b":[{"tags":["Tag A"]},{"tags":["Tag B"]}]}'
 *
 * stringifyWithoutQuotes(data)
 * '{a:1,b:[{tags:["Tag A"]},{tags:["Tag B"]}]}'
 */

export const stringifyWithoutQuotes = (obj: object): string => {
  return JSON.stringify(obj, null, 4).replace(/"([^"]+)":/g, "$1:");
};

export const cleanTabsAndNewLines = (string: string) => {
  return string.replaceAll(/\t*\n*/g, "").replaceAll(/\s+/g, " ");
};

export const capitalizeFirstLetter = (string: string) => {
  return string.charAt(0).toUpperCase() + string.slice(1);
};

export const concatString = (acc: string, elem: string) => `${acc}${elem}`;
