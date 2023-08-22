import Handlebars from "handlebars";

export const createBranch = Handlebars.compile(`
mutation {
  BranchCreate (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
