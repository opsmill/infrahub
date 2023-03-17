import { gql } from "@apollo/client";
import { CheckIcon, XMarkIcon } from "@heroicons/react/24/outline";

import { useAtom } from "jotai";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { graphQLClient } from "../..";
import { classNames } from "../../App";
import { branchState } from "../../state/atoms/branch.atom";
import { comboxBoxFilterState } from "../../state/atoms/filters.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { timeState } from "../../state/atoms/time.atom";
import DeviceFilterBar from "../device-list/device-filter-bar";
import DeviceFilters from "../device-list/device-filters";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind}} {
        {{name}}{{#if filterString}}({{{filterString}}}){{/if}} {
            id
            display_label
            {{#each attributes}}
              {{this.name}} {
                  value
              }
            {{/each}}
            {{#each relationships}}
              {{this.name}} {
                  display_label
              }
            {{/each}}
        }
    }
`);

const getItemsColumn = (schema: any) => {
  const relationsShipsColumns = schema?.relationships?.filter((relationship: any) => relationship?.cardinality === "one");

  return [
    ...(schema?.attributes ?? []),
    ...(relationsShipsColumns ?? [])
  ]
  .sort(
    (a, b) => {
      if (a.label && b.label) {
        return a.label.localeCompare(b.label);
      }
      return -1;
    }
  )
}

const getObjectItemDisplayValue = (row: any, attribute: any) => {
  // Get "value" or "display_name" depending on the kind (attribute or relationship)
  const value = row[attribute?.name]?.value ?? row[attribute?.name]?.display_label ?? "-";

  if (row?.value === false) {
    return (
      <XMarkIcon className="h-4 w-4" />
    );
  }

  if (row?.value === true) {
    return (
      <CheckIcon className="h-4 w-4" />
    );
  }

  return value;
}

export default function ObjectItems() {
  let { objectname } = useParams();
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [objectRows, setObjectRows] = useState<any[] | undefined>();
  const [schemaList] = useAtom(schemaState);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const [currentFilters] = useAtom(comboxBoxFilterState);

  const filterString = currentFilters
  .map((row) => `${row.name}: "${row.value}"`)
  .join(",");

  // Get all teh needed columns (attributes + relationships with a cardinality of "one")
  const columns = getItemsColumn(schema);

  const navigate = useNavigate();

  useEffect(
    () => {
      const loadData = async () => {
        if (schema) {
          try {

            setHasError(false);
            setIsLoading(true);
            setObjectRows(undefined);

            const queryString = template({
              ...schema,
              filterString,
              columns
            });

            const query = gql`
            ${queryString}
            `;

            const data = await graphQLClient.request(query);
            const rows = data[schema.name];
            setObjectRows(rows);
            setIsLoading(false);

          } catch(e) {
            console.error("Error: ", e);
            setHasError(true);
            setIsLoading(false);
          };
        }
      }

      loadData();
    },
    [
      objectname,
      schemaList,
      schema,
      date,
      branch,
      currentFilters,
      filterString,
    ]
  );

  if (hasError) {
    return <ErrorScreen />;
  }

  // if (isLoading && !objectRows) {
  //   return <LoadingScreen />;
  // }

  return (
    <div className="flex-1 pt-0 px-4 sm:px-0 md:px-0 overflow-x-auto flex flex-col">
      <div className="sm:flex sm:items-center py-4 px-4 sm:px-6 lg:px-8 w-full">
        {
          schema
          && (
            <div className="sm:flex-auto flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">
                {schema.kind} ({objectRows?.length})
              </h1>
              <p className="mt-2 text-sm text-gray-700 m-0 pl-2 mb-1">
                A list of all the {schema.kind} in your infrastructure.
              </p>
            </div>
          )
        }

        <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
          <DeviceFilters />
        </div>
      </div>

      {
        schema
        && <DeviceFilterBar schema={schema} />
      }

      {
        isLoading
        && !objectRows
        && <LoadingScreen />
      }

      {
        !isLoading
        && objectRows
        && (
          <div className="mt-0 flex flex-col px-4 sm:px-6 lg:px-8 w-full overflow-x-auto flex-1">
            <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
              <div className="inline-block min-w-full pt-2 align-middle">
                <div className="shadow-sm ring-1 ring-black ring-opacity-5">
                  <table
                    className="min-w-full border-separate"
                    style={{ borderSpacing: 0 }}
                  >
                    <thead className="bg-gray-50">
                      <tr>
                        {
                          columns
                          ?.map(
                            (attribute) => (
                              <th
                                key={attribute.name}
                                scope="col"
                                className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8"
                              >
                                {attribute.label}
                              </th>
                            )
                          )
                        }
                      </tr>
                    </thead>
                    <tbody className="bg-white">
                      {
                        objectRows
                        ?.map(
                          (row, index) => (
                            <tr
                              onClick={() => {
                                navigate(`/objects/${schema.name}/${row.id}`);
                              }}
                              key={index}
                              className="hover:bg-gray-50"
                            >
                              {columns?.map((attribute) => (
                                <td
                                  key={row.id + "-" + attribute.name}
                                  className={classNames(
                                    index !== objectRows.length - 1
                                      ? "border-b border-gray-200"
                                      : "",
                                    "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                                  )}
                                >
                                  {getObjectItemDisplayValue(row, attribute)}
                                </td>
                              ))}
                            </tr>
                          )
                        )
                      }
                    </tbody>
                  </table>

                  {
                    !objectRows
                    ?.length
                    && <NoDataFound />
                  }
                </div>
              </div>
            </div>
          </div>
        )}
    </div>
  );
}
