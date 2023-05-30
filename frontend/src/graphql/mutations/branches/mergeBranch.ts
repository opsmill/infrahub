import Handlebars from "handlebars";

export const mergeBranch = Handlebars.compile(`
mutation {
  branch_merge (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
