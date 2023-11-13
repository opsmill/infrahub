import Handlebars from "handlebars";

export const validateBranch = Handlebars.compile(`
mutation {
  BranchValidate (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
