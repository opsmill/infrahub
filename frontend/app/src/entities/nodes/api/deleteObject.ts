import Handlebars from "@/shared/libs/handlebars";

export const deleteObject = Handlebars.compile(`
mutation {{kind}}Delete {
  {{kind}}Delete (data: {{{data}}}) {
      ok
  }
}
`);
