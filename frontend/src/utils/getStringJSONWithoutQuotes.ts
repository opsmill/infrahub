/**
 * Same as JSON.stringify, but this will remove the quotes around keys/properties from the output
 *
 * const data = {a: 1, b: [{tags: ["Tag A"]}, {tags: ["Tag B"]}]}
 *
 * JSON.stringify(data)
 * '{"a":1,"b":[{"tags":["Tag A"]},{"tags":["Tag B"]}]}'
 *
 * getStringJSONWithoutQuotes(data)
 * '{a:1,b:[{tags:["Tag A"]},{tags:["Tag B"]}]}'
 */

export const getStringJSONWithoutQuotes = (obj: object): string => {
  return JSON.stringify(obj, null, 4).replace(/"([^"]+)":/g, "$1:");
};
