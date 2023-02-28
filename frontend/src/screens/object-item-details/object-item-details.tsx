import { useAtom } from "jotai";
import { gql } from "@apollo/client";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { graphQLClient } from "../..";
import { schemaState } from "../../state/atoms/schema.atom";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import DeviceFilters from "../device-list/device-filters";
import DeviceFilterBar from "../device-list/device-filter-bar";
import { classNames } from "../../App";
import { HomeIcon, PaperClipIcon } from "@heroicons/react/24/outline";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import { timeState } from "../../state/atoms/time.atom";
import { branchState } from "../../state/atoms/branch.atom";
import NoDataFound from "../no-data-found/no-data-found";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
        {{name}} (ids: ["{{objectid}}"]) {
            id
            {{#each attributes}}
            {{this.name}} {
                value
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

  const [objectRows, setObjectRows] = useState<any[] | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const navigate = useNavigate();

  useEffect(() => {
    if (schema) {
      setHasError(false);
      setIsLoading(true);
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
  }, [objectname, schemaList, schema, date, branch]);

  if (hasError) {
    return <ErrorScreen />;
  }

  if (isLoading && !objectRows) {
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

  const row = (objectRows || [])[0];

  return (
    <div className="overflow-hidden bg-white">
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
          {columns.map((column) => (
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6" key={column}>
              <dt className="text-sm font-medium text-gray-500">{column}</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {column === "id" ? row[column] : row[column].value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
