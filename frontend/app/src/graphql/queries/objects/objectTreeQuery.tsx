import Handlebars from "handlebars";

export const objectTopLevelTreeQuery = Handlebars.compile(`
  query GET_{{kind}}_TOP_LEVEL_TREE {
    {{kind}}(parent__isnull: true, limit: null) {
      edges {
        node {
          id
          display_label
          children {
            count
          }
          parent {
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

export const objectChildrenQuery = Handlebars.compile(`
  query GET_{{kind}}_CHILDREN($parentIds: [ID!]) {
    {{kind}}(parent__ids: $parentIds) {
      edges {
        node {
          id
          display_label
          parent {
            node {
              id
            }
          }
          children {
            count
          }
        }
      }
    }
  }
`);

export const objectAncestorsQuery = Handlebars.compile(`
  query GET_{{kind}}_ANCESTORS($ids: [ID]) {
    {{kind}}(ids: $ids) {
      edges {
        node {
          id
          display_label
          parent {
            node {
              id
              display_label
            }
          }
          children {
            count
          }
          ancestors {
            edges {
              node {
                id
                display_label
                parent {
                  node {
                    id
                    display_label
                  }
                }
                children {
                  count
                  edges {
                    node {
                      id
                      display_label
                      parent {
                        node {
                          id
                          display_label
                        }
                      }
                      children {
                        count
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
`);
