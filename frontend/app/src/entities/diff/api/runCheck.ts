import Handlebars from "@/shared/libs/handlebars";

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
