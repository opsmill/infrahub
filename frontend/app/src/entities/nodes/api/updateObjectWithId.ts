import Handlebars from "@/shared/libs/handlebars";

export const updateObjectWithId = Handlebars.compile(`
mutation {{kind}}Update {
  {{kind}}Update (data: {{{data}}}) {
      ok
  }
}
`);
