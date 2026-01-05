import Handlebars from "@/shared/libs/handlebars";

export const getArtifactDetails = Handlebars.compile(`
query CoreArtifact {
  CoreArtifact (ids: ["{{id}}"]) {
    edges {
      node {
        id
        object {
            node {
              id
              display_label
            }
        }
      }
    }
  }
}
`);
