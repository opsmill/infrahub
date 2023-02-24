import { gql, useQuery } from "@apollo/client";
import { useState } from "react";
import { classNames } from "../../App";
import { Maybe, NodeSchema } from "../../generated/graphql";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectRows from "./object-rows";

const SCHEMA_QUERY = gql`
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

interface SchemaData {
  node_schema: Maybe<Array<Maybe<NodeSchema>>>;
}

export default function OpsObjects() {
  const { loading, data, error } = useQuery<SchemaData>(SCHEMA_QUERY);
  const [selectedSchema, setSelectedSchema] = useState<NodeSchema>();

  if(error) {
    return <ErrorScreen />
  }

  return (
    <div className="flex overflow-auto">
      <div className="flex-1 overflow-auto">
        {loading && <LoadingScreen />}
        <div className="p-4 space-y-4 bg-gray-50">
          {data?.node_schema?.map((schema) => (
            <div
              key={schema?.name.value}
              className={classNames(
                "p-4 shadow-lg border border-gray-200 bg-white rounded-md hover:bg-gray-100 cursor-pointer",
                selectedSchema?.name.value === schema?.name.value
                  ? "border-blue-500"
                  : ""
              )}
              onClick={() => {
                if (schema) {
                  setSelectedSchema(schema);
                }
              }}
            >
              {schema?.kind.value} - {schema?.name.value}
              <div>{schema?.attributes?.length} attribute(s)</div>
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {selectedSchema && <ObjectRows schema={selectedSchema} />}
      </div>
    </div>
  );
}
