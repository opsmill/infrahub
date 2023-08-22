import Handlebars from "handlebars";

export const rebaseBranch = Handlebars.compile(`
mutation {
  BranchRebase (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
