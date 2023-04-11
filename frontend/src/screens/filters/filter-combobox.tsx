import { Combobox } from "@headlessui/react";
import { CheckIcon, ChevronUpDownIcon } from "@heroicons/react/20/solid";
import { gql } from "graphql-request";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { graphQLClient } from "../../graphql/graphqlClient";
import { components } from "../../infraops";
import { comboxBoxFilterState } from "../../state/atoms/filters.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { classNames } from "../../utils/common";
import LoadingScreen from "../loading-screen/loading-screen";

declare const Handlebars: any;

interface Props {
  filter: components["schemas"]["FilterSchema"];
}

const template = Handlebars.compile(`query {{kind.value}} {
    {{name}} {
        id
        display_label
    }
}
`);

export default function FilterCombobox(props: Props) {
  const { filter } = props;
  const [schemaList] = useAtom(schemaState);
  const [filters, setFilters] = useAtom(comboxBoxFilterState);
  const schema = schemaList.filter((s) => filter.object_kind === s.kind)[0];
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [objectRows, setObjectRows] = useState<any[] | undefined>();
  const [query, setQuery] = useState("");
  const currentFilter = filters.filter((row) => row.name === filter.name);

  const fetchFilterRows = useCallback(
    async () => {
      if (schema && !filter.enum) {
        setHasError(false);
        setIsLoading(true);
        // TODO: Extract GQL function in the graphql/ fodler
        const queryString = template(schema);
        const query = gql`
        ${queryString}
      `;
        try {
          const data: any = await graphQLClient.request(query);
          const rows = data[schema.name];
          setObjectRows(rows);
          setIsLoading(false);
        } catch {
          setHasError(true);
          setIsLoading(false);
        }
      } else if (filter.enum) {
        setObjectRows(
          filter.enum.map((en) => ({
            id: en,
            display_label: en,
          }))
        );
      }
    },
    [filter.enum, schema]
  );

  useEffect(
    () => {
      fetchFilterRows();
    },
    [schemaList, schema, filter, fetchFilterRows]
  );

  if (hasError) {
    return (
      <div className="text-red-500">{filter.name} {schema.name}</div>
    );
    // return <ErrorScreen />;
  }

  if (isLoading) {
    return <LoadingScreen hideText={true} size="10" />;
  }

  const filteredRows =
    query === ""
      ? objectRows
      : objectRows?.filter((row) => row.display_label.toLowerCase().includes(query.toLowerCase()));

  return (
    <Combobox
      as="div"
      value={currentFilter.length ? currentFilter[0] : null}
      onChange={(selected: any) => {
        setFilters([
          ...filters.filter((row) => row.name !== filter.name),
          {
            value: selected.id,
            display_label: selected.display_label,
            name: filter.name,
          },
        ]);
      }}
    >
      <Combobox.Label className="block text-sm font-medium text-gray-700">
        {filter.name}
      </Combobox.Label>

      <div className="relative mt-2">
        <Combobox.Input
          className="w-full rounded-md border border-gray-300 bg-white py-2 pl-3 pr-10 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:text-sm"
          onChange={(event) => setQuery(event.target.value)}
          displayValue={(row: any) => (row ? row.display_label : "")}
        />

        <Combobox.Button className="absolute inset-y-0 right-0 flex items-center rounded-r-md px-2 focus:outline-none">
          <ChevronUpDownIcon
            className="h-5 w-5 text-gray-400"
            aria-hidden="true"
          />
        </Combobox.Button>

        {
          filteredRows
          && filteredRows?.length > 0
          && (
            <Combobox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
              {
                filteredRows
                ?.map(
                  (row) => (
                    <Combobox.Option
                      key={row.id}
                      value={row}
                      className={({ active }) =>
                        classNames(
                          "relative cursor-default select-none py-2 pl-3 pr-9",
                          active ? "bg-indigo-600 text-white" : "text-gray-900"
                        )
                      }
                    >
                      {
                        ({ active, selected }) => (
                          <>
                            <span
                              className={classNames(
                                "block truncate",
                                selected ? "font-semibold" : ""
                              )}
                            >
                              {row.display_label}
                            </span>

                            {
                              selected
                            && (
                              <span
                                className={classNames(
                                  "absolute inset-y-0 right-0 flex items-center pr-4",
                                  active ? "text-white" : "text-indigo-600"
                                )}
                              >
                                <CheckIcon className="h-5 w-5" aria-hidden="true" />
                              </span>
                            )
                            }
                          </>
                        )
                      }
                    </Combobox.Option>
                  )
                )}
            </Combobox.Options>
          )}
      </div>
    </Combobox>
  );
}
