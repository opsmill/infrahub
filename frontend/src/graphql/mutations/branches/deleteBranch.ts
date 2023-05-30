import Handlebars from "handlebars";

export const deleteBranch = Handlebars.compile(`
mutation {
  branch_delete (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
