declare const Handlebars: any;

export const rebaseBranch = Handlebars.compile(`
mutation {
  branch_rebase (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
