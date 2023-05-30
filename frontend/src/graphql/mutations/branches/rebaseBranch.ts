import Handlebars from "handlebars";

export const rebaseBranch = Handlebars.compile(`
mutation {
  branch_rebase (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
