import { gql, useQuery } from "@apollo/client";
import { useAtom } from "jotai";
import { useEffect, useState } from "react";
import { graphQLClient } from "../..";
import { classNames } from "../../App";
import { Maybe, NodeSchema } from "../../generated/graphql";
import { schemaState } from "../../state/atoms/schema.atom";
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
  node_schema: Maybe<Array<NodeSchema>>;
}

export default function OpsObjects() {
  const [schema, setSchema] = useAtom(schemaState);
  const [selectedSchema, setSelectedSchema] = useState<NodeSchema>();
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const request = graphQLClient.request(SCHEMA_QUERY);
    request.then((data: SchemaData) => {
      if (data.node_schema?.length) {
        setSchema(data.node_schema);
      }
      setIsLoading(false);
    }).catch(() => {
      setHasError(true);
    });
  }, []);

  if (hasError) {
    return <ErrorScreen />;
  }

  return (
    <div className="flex overflow-auto">
      <div className="flex-1 overflow-auto">
        {isLoading && <LoadingScreen />}
        <div className="p-4 space-y-4 bg-gray-50">
          {schema.map((schema) => (
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
