import { VariableType } from "json-to-graphql-query";

interface HoistedMutationData {
  data: Record<string, unknown>;
  variableDefinitions: Record<string, string>;
  variableValues: Record<string, unknown>;
}

const hasComplexValue = (
  fieldInput: unknown
): fieldInput is Record<string, unknown> & { value: object } => {
  if (typeof fieldInput !== "object" || fieldInput === null || Array.isArray(fieldInput)) {
    return false;
  }
  const { value } = fieldInput as Record<string, unknown>;
  return typeof value === "object" && value !== null;
};

/**
 * GraphQL object literals only accept keys matching the Name grammar
 * (`[_A-Za-z][_0-9A-Za-z]*`), while JSON and List attribute values may contain
 * arbitrary keys (e.g. `{"auth-token": "..."}`). Such values cannot be inlined
 * in a mutation document; they must be sent as GraphQL variables instead.
 *
 * Replaces every attribute input value that is an object or array with a
 * `$value_<fieldName>` variable reference, and returns the matching variable
 * definitions (typed `GenericScalar`) and values to attach to the request.
 * Relationship inputs carry no `value` key and pass through untouched.
 */
export const hoistAttributeValuesToVariables = (
  data: Record<string, unknown>
): HoistedMutationData => {
  const variableDefinitions: Record<string, string> = {};
  const variableValues: Record<string, unknown> = {};

  const dataWithVariableReferences = Object.fromEntries(
    Object.entries(data).map(([fieldName, fieldInput]) => {
      if (!hasComplexValue(fieldInput)) {
        return [fieldName, fieldInput];
      }

      const variableName = `value_${fieldName}`;
      variableDefinitions[variableName] = "GenericScalar";
      variableValues[variableName] = fieldInput.value;
      return [fieldName, { ...fieldInput, value: new VariableType(variableName) }];
    })
  );

  return { data: dataWithVariableReferences, variableDefinitions, variableValues };
};
