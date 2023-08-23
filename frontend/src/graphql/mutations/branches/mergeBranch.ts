import Handlebars from "handlebars";

export const mergeBranch = Handlebars.compile(`
mutation {
  BranchMerge (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
