import { gql, useQuery } from "@apollo/client";
import { FunnelIcon } from "@heroicons/react/20/solid";
import { useAtom } from "jotai";
import { FormProvider, useForm } from "react-hook-form";
import { Button } from "../../components/button";
import { getDropdownOptionsForRelatedPeersPaginated } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import { iComboBoxFilter } from "../../graphql/variables/filtersVar";
import useFilters from "../../hooks/useFilters";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { resolve } from "../../utils/objects";
import { DynamicControl } from "../edit-form-hook/dynamic-control";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

// const sortOptions = [
//   { name: "Name", href: "#", current: true },
//   { name: "Status", href: "#", current: false },
//   { name: "ASN", href: "#", current: false },
// ];

// TODO: Functionnal programming update
// TODO: Pagination with infitie scrolling for the select
export default function DeviceFilterBarContent(props: any) {
  const { objectname } = props;

  const [filters, setFilters] = useFilters();
  const [schemaList] = useAtom(schemaState);
  const [genericList] = useAtom(genericsState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const generic = genericList.filter((s) => s.name === objectname)[0];

  const schemaData = schema || generic;

  const peers: string[] = [];

  (schemaData.filters || []).forEach((f) => {
    if (f.kind === "Object" && f.object_kind) {
      peers.push(f.object_kind);
    }
  });

  const queryString = getDropdownOptionsForRelatedPeersPaginated({
    peers,
  });

  const query = peers.length
    ? gql`
        ${queryString}
      `
    : gql`
        query {
          __type(name: "DataSource") {
            fields {
              name
              description
            }
          }
        }
      `;

  const { loading, error, data = {} } = useQuery(query, { skip: !schemaData });

  const peerDropdownOptions: any = data;

  const formFields: DynamicFieldData[] = [];

  schemaData.filters?.forEach((filter) => {
    const currentValue = filters?.find((f: iComboBoxFilter) => f.name === filter.name);
    if (filter.kind === "Text" && !filter.enum) {
      formFields.push({
        label: filter.name,
        name: filter.name,
        type: "text",
        value: currentValue ?? "",
      });
    } else if (filter.kind === "Text" && filter.enum) {
      formFields.push({
        label: filter.name,
        name: filter.name,
        type: "select",
        value: currentValue ?? "",
        options: {
          values: filter.enum?.map((row: any) => ({
            name: row,
            id: row,
          })),
        },
      });
    } else if (filter.kind === "Object") {
      if (filter.object_kind && peerDropdownOptions && peerDropdownOptions[filter.object_kind]) {
        const { edges } = peerDropdownOptions[filter.object_kind];

        const options = edges.map((row: any) => ({
          name: row.node.display_label,
          id: row.node.id,
        }));

        formFields.push({
          label: filter.name,
          name: filter.name,
          type: "select",
          value: currentValue ? currentValue.value : "",
          options: {
            values: options,
          },
        });
      }
    }
  });

  const onSubmit = (data: any) => {
    const keys = Object.keys(data);

    const filters: iComboBoxFilter[] = [];

    for (let filterKey of keys) {
      const filterValue = data[filterKey];

      if (data[filterKey]) {
        filters.push({
          display_label: filterKey,
          name: filterKey,
          value: filterValue,
        });
      }
    }

    setFilters(filters);
  };

  const formMethods = useForm();

  const {
    handleSubmit,
    formState: { errors },
  } = formMethods;

  const FilterField = (props: any) => {
    const { field, error } = props;

    return (
      <div className="p-2 mr-2">
        <DynamicControl {...field} error={error} />
      </div>
    );
  };

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the filters." />;
  }

  if (loading || !schemaData) {
    return <LoadingScreen />;
  }

  if (!data) {
    return <NoDataFound />;
  }

  return (
    <div className="border-t border-gray-200 pb-10">
      <div className="mx-auto px-4 text-sm sm:px-6">
        <div>
          <form className="flex-1" onSubmit={handleSubmit(onSubmit)}>
            <FormProvider {...formMethods}>
              <div className="mb-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
                {formFields.map((field: DynamicFieldData, index: number) => (
                  <FilterField key={index} field={field} error={resolve("field.name", errors)} />
                ))}
              </div>
              <Button className="ml-2" type="submit">
                Filter
                <FunnelIcon className="w-4 h-4 text-gray-500" />
              </Button>
            </FormProvider>
          </form>
        </div>
      </div>
    </div>
  );
}
