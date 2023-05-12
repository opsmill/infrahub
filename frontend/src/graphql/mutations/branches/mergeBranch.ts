declare const Handlebars: any;

export const mergeBranch = Handlebars.compile(`
mutation {
  branch_merge (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
