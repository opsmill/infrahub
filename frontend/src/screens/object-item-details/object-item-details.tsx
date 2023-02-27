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
import { PaperClipIcon } from "@heroicons/react/24/outline";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
        {{name.value}} (ids: ["{{objectid}}"]) {
            id
            {{#each attributes}}
            {{this.name.value}} {
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
  const [objectRows, setObjectRows] = useState<any[]>([]);
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name.value === objectname)[0];

  const navigate = useNavigate();

  useEffect(() => {
    if (schema) {
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
          const rows = data[schema.name.value!];
          setObjectRows(rows);
          setIsLoading(false);
        })
        .catch(() => {
          setHasError(true);
        });
    }
  }, [objectname, schemaList, schema]);

  if (hasError) {
    return <ErrorScreen />;
  }

  if (isLoading || objectRows.length === 0) {
    return <LoadingScreen />;
  }

  let columns: string[] = [];

  if (objectRows.length) {
    const firstRow = objectRows[0];
    columns = Object.keys(firstRow);
  }

  const row = objectRows[0];

  return (
    <div className="overflow-hidden bg-white">
      <div className="px-4 py-5 sm:px-6">
        <h3 className="text-base font-semibold leading-6 text-gray-900">
          {schema.kind.value}
        </h3>
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{row.id}</p>
      </div>
      <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
        <dl className="sm:divide-y sm:divide-gray-200">
          {columns.map((column) => (
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
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
