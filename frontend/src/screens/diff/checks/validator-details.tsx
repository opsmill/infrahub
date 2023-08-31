import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useEffect } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../../config/qsp";
import { getValidatorDetails } from "../../../graphql/queries/diff/getValidatorDetails";
import useQuery from "../../../hooks/useQuery";
import { iNodeSchema, schemaState } from "../../../state/atoms/schema.atom";
import { getObjectItemDisplayValue } from "../../../utils/getObjectItemDisplayValue";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";

const getValidatorAttributes = (typename: string, schemaList: iNodeSchema[]) => {
  const schema = schemaList.find((schema: iNodeSchema) => schema.kind === typename);

  if (!schema) return [];

  return schema.attributes;
};

export const ValidatorDetails = () => {
  const [schemaList] = useAtom(schemaState);
  const [qspTab, setQsp] = useQueryParam(QSP.VALIDATOR_DETAILS, StringParam);

  const queryString = getValidatorDetails({
    id: qspTab,
  });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query);

  useEffect(() => {
    return () => {
      // When unmounting, remove validator details view QSP
      setQsp(undefined);
    };
  }, []);

  if (loading) {
    return <LoadingScreen />;
  }

  if (error) {
    return <ErrorScreen />;
  }

  const validator = data?.CoreValidator?.edges[0]?.node;

  const attributes = getValidatorAttributes(validator?.__typename, schemaList);

  return (
    <div className="flex-1 overflow-auto flex flex-col">
      <div className="bg-custom-white px-4 py-5 pb-0 sm:px-6 flex items-center">
        <div
          onClick={() => setQsp(undefined)}
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline">
          Checks
        </div>
        <ChevronRightIcon
          className="h-5 w-5 mt-1 mx-2 flex-shrink-0 text-gray-400"
          aria-hidden="true"
        />
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{validator?.display_label}</p>
      </div>

      <div className="flex flex-col">
        <div className="bg-custom-white p-4 overflow-auto">
          <dl className="sm:divide-y sm:divide-gray-200">
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6">
              <dt className="text-sm font-medium text-gray-500 flex items-center">ID</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">{validator.id}</dd>
            </div>

            {attributes?.map((attribute) => {
              return (
                <div
                  className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6"
                  key={attribute.name}>
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    {attribute.label}
                  </dt>

                  <div className="flex items-center">
                    <dd className={"mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0"}>
                      {getObjectItemDisplayValue(validator, attribute)}
                    </dd>
                  </div>
                </div>
              );
            })}
          </dl>
        </div>
      </div>
    </div>
  );
};
