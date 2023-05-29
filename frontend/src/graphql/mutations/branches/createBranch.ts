import Handlebars from "handlebars";

export const createBranch = Handlebars.compile(`
mutation {
  branch_create (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
