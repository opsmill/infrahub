import Handlebars from "handlebars";

export const deleteBranch = Handlebars.compile(`
mutation {
  BranchDelete (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
