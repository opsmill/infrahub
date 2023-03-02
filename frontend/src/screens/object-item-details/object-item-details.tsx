import { useAtom } from "jotai";
import { gql } from "@apollo/client";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { graphQLClient } from "../..";
import { schemaState } from "../../state/atoms/schema.atom";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import { timeState } from "../../state/atoms/time.atom";
import { branchState } from "../../state/atoms/branch.atom";
import NoDataFound from "../no-data-found/no-data-found";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { CheckIcon } from "@heroicons/react/24/outline";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
        {{name}} (ids: ["{{objectid}}"]) {
            id
            {{#each attributes}}
            {{this.name}} {
                value
            }
            {{/each}}
            {{#each relationships}}
            {{this.name}} {
                id
                display_label
            }
            {{/each}}
        }
    }
`);

export default function ObjectItemDetails() {
  let { objectname, objectid } = useParams();
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);
  const [schemaKindName] = useAtom(schemaKindNameState);

  const [objectRows, setObjectRows] = useState<any[] | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const navigate = useNavigate();

  useEffect(() => {
    if (schema) {
      setHasError(false);
      setIsLoading(true);
      setObjectRows(undefined);
      const queryString = template({
        ...schema,
        objectid,
      });
      const query = gql`
        ${queryString}
      `;
      const request = graphQLClient.request(query);
      request
        .then((data) => {
          const rows = data[schema.name];
          setObjectRows(rows);
          setIsLoading(false);
        })
        .catch(() => {
          setHasError(true);
          setIsLoading(false);
        });
    }
  }, [objectname, objectid, schemaList, schema, date, branch]);

  const row = (objectRows || [])[0];

  if (hasError) {
    return <ErrorScreen />;
  }

  if ((isLoading && !objectRows) || !objectRows?.length || !row) {
    return <LoadingScreen />;
  }

  if (objectRows && objectRows.length === 0) {
    return <NoDataFound />;
  }

  let columns: string[] = [];

  if (objectRows && objectRows.length) {
    const firstRow = objectRows[0];
    columns = Object.keys(firstRow);
  }

  return (
    <div className="bg-white flex-1 overflow-auto">
      <div className="px-4 py-5 sm:px-6 flex items-center">
        <div
          onClick={() => {
            navigate(-1);
          }}
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
        >
          {schema.kind}
        </div>
        <ChevronRightIcon
          className="h-5 w-5 mt-1 mx-2 flex-shrink-0 text-gray-400"
          aria-hidden="true"
        />
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{row.id}</p>
      </div>
      <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
        <dl className="sm:divide-y sm:divide-gray-200">
          <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
            <dt className="text-sm font-medium text-gray-500">ID</dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
              {row.id}
            </dd>
          </div>
          {schema.attributes?.map((attribute) => (
            <div
              className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
              key={attribute.name}
            >
              <dt className="text-sm font-medium text-gray-500">
                {attribute.name}
              </dt>
              {row[attribute.name] && (
                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                  {row[attribute.name].value || "-"}
                  {row[attribute.name].value === true && (
                    <CheckIcon className="h-4 w-4" />
                  )}
                </dd>
              )}
            </div>
          ))}
          {schema.relationships?.map((relationship) => (
            <div
              className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
              key={relationship.name}
            >
              <dt className="text-sm font-medium text-gray-500">
                {relationship.name}
              </dt>
              {row[relationship.name] && (
                <>
                  {relationship.cardinality === "one" && (
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline">
                      <Link
                        to={`/objects/${schemaKindName[relationship.peer]}/${
                          row[relationship.name].id
                        }`}
                      >
                        {row[relationship.name].display_label}
                      </Link>
                    </dd>
                  )}
                  {relationship.cardinality === "many" && (
                    <div className="sm:col-span-2 space-y-4">
                      {row[relationship.name].map((item: any) => (
                        <dd className="mt-1 text-sm text-gray-900 sm:mt-0 underline">
                          <Link
                            key={item.id}
                            to={`/objects/${
                              schemaKindName[relationship.peer]
                            }/${item.id}`}
                          >
                            {item.display_label}
                          </Link>
                        </dd>
                      ))}
                    </div>
                  )}
                </>
              )}
              {!row[relationship.name] && <>-</>}
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
