import { gql } from "@apollo/client";
import { NodeSchema } from "../../generated/graphql";

export interface iSchemaData {
  node_schema: Array<NodeSchema>;
}

export const SCHEMA_QUERY = gql`
  query {
    node_schema {
      name {
        value
      }
      kind {
        value
      }
      inherit_from {
        value
      }
      description {
        value
      }
      default_filter {
        value
      }
      attributes {
        name {
          value
        }
        optional {
          value
        }
        unique {
          value
        }
        default_value {
          value
        }
      }
      relationships {
        name {
          value
        }
        peer {
          value
        }
        identifier {
          value
        }
        cardinality {
          value
        }
        optional {
          value
        }
      }
    }
  }
`;
