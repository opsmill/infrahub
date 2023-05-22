declare const Handlebars: any;

export const createBranch = Handlebars.compile(`
mutation {
  branch_create (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
