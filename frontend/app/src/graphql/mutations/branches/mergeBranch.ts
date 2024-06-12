import Handlebars from "handlebars";

export const mergeBranch = Handlebars.compile(`
mutation BranchMerge {
  BranchMerge (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
