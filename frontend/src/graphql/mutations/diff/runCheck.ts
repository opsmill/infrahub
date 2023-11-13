import Handlebars from "handlebars";

export const runCheck = Handlebars.compile(`
mutation {
  CoreProposedChangeRunCheck (
    data: {
      id: "{{id}}",
      check_type: {{check_type}}
    }
  ) {
      ok
  }
}
`);
