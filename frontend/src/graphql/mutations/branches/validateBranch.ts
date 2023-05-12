declare const Handlebars: any;

export const validateBranch = Handlebars.compile(`
mutation {
  branch_validate (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
