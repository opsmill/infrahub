import { gql, useQuery } from "@apollo/client";
import { FunnelIcon } from "@heroicons/react/20/solid";
import { useAtom } from "jotai";
import { FormProvider, useForm } from "react-hook-form";
import { Button } from "../../components/buttons/button";
import { getDropdownOptionsForRelatedPeersPaginated } from "../../graphql/queries/objects/dropdownOptionsForRelatedPeers";
import useFilters from "../../hooks/useFilters";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import getFormStructureForFilters from "../../utils/formStructureForFilters";
import { resolve } from "../../utils/objects";
import { DynamicControl } from "../edit-form-hook/dynamic-control";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

// TODO: Functionnal programming update
// TODO: Pagination with infitie scrolling for the select
export default function DeviceFilterBarContent(props: any) {
  const { objectname } = props;

  const [filters, setFilters] = useFilters();
  const [schemaList] = useAtom(schemaState);
  const [genericList] = useAtom(genericsState);
  const schema = schemaList.find((s) => s.kind === objectname);
  const generic = genericList.find((s) => s.kind === objectname);

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

  const formFields = getFormStructureForFilters(schemaData, filters, data);

  const onSubmit = (data: any) => {
    const newFilters = Object.entries(data)
      .map(
        ([key, value]) =>
          value && {
            display_label: key,
            name: key,
            value,
          }
      )
      .filter(Boolean);

    setFilters(newFilters);
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
    return <NoDataFound message="No filters found." />;
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
