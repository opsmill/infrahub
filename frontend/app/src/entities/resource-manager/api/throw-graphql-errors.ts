export const throwGraphQLErrors = (errors: ReadonlyArray<{ message: string }> | undefined) => {
  if (errors?.length) throw new Error(errors.map(({ message }) => message).join("; "));
};
