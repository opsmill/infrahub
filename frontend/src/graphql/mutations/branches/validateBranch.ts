import Handlebars from "handlebars";

export const validateBranch = Handlebars.compile(`
mutation {
  branch_validate (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
