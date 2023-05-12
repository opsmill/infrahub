declare const Handlebars: any;

export const deleteBranch = Handlebars.compile(`
mutation {
  branch_delete (
    data: { {{{data}}} }
  ) {
      ok
  }
}
`);
