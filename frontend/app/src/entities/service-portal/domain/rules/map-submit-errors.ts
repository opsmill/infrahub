import { FROM_RESOURCE_POOL_SUFFIX } from "@/shared/components/form/constants";

export interface SubmitErrors {
  fieldErrors: Record<string, string>;
  formError: string | null;
}

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const fieldKeyPattern = (fieldName: string) =>
  `${escapeRegExp(fieldName)}(${escapeRegExp(FROM_RESOURCE_POOL_SUFFIX)})?(\\W|$)`;

// Backend validation messages read "<message> at <input key>"; fall back to any whole-word mention.
const findField = (message: string, fieldNames: Array<string>) =>
  fieldNames.find((name) => new RegExp(`(^|\\W)at ${fieldKeyPattern(name)}`).test(message)) ??
  fieldNames.find((name) => new RegExp(`(^|\\W)${fieldKeyPattern(name)}`).test(message));

// The GraphQL client joins error messages with "; ".
// Each message is attached to one field: a message naming several fields goes to the first match.
export const mapSubmitErrors = (message: string, fieldNames: Array<string>): SubmitErrors => {
  const fieldErrors: Record<string, string> = {};
  const formErrors: Array<string> = [];

  for (const part of message.split("; ")) {
    const fieldName = findField(part, fieldNames);
    if (fieldName) {
      fieldErrors[fieldName] = fieldErrors[fieldName] ? `${fieldErrors[fieldName]}; ${part}` : part;
    } else {
      formErrors.push(part);
    }
  }

  return { fieldErrors, formError: formErrors.length ? formErrors.join("; ") : null };
};
