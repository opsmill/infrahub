import { gql, useQuery } from "@apollo/client";
import {
  ShieldCheckIcon,
  StarIcon,
} from "@heroicons/react/24/outline";
import { useEffect, useState } from "react";
import { graphQLClient } from "../..";
import { NodeSchema } from "../../generated/graphql";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
        {{name.value}} {
            {{#each attributes}}
            {{this.name.value}} {
                value
            }
            {{/each}}
        }
    }
`);

const getDisplayAttribute = (schema: NodeSchema): string => {
  const requiredAttributes = schema.attributes?.filter(
    (attribute) => attribute?.optional.value === false
  );
  const attributesWithDefaultValue = schema.attributes?.filter(
    (attribute) => !!attribute?.default_value?.value
  );
  const nameAttribute = schema.attributes?.filter(
    (attribute) => attribute?.name.value === "name"
  );

  if (nameAttribute?.length) {
    return "name";
  } else if (requiredAttributes?.length) {
    return requiredAttributes[0]?.name.value!;
  } else if (attributesWithDefaultValue?.length) {
    return attributesWithDefaultValue[0]?.name.value!;
  } else {
    return "";
  }
};

interface Props {
  schema: NodeSchema;
}

export default function ObjectRows(props: Props) {
  const { schema } = props;
  const queryString = template(schema);
  const query = gql`
    ${queryString}
  `;
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [objectRows, setObjectRows] = useState([]);

  useEffect(() => {
    const request = graphQLClient.request(query);
    request.then((data) => {
      const rows = data[schema.name.value!];
      setObjectRows(rows);
      setIsLoading(false);
    }).catch(() => {
      setHasError(true);
    });
  }, []);

  if(hasError) {
    return <ErrorScreen />
  }

  if (isLoading) {
    return <LoadingScreen />;
  }

  const displayAttribute = getDisplayAttribute(props.schema);

  return (
    <div className="p-4">
      <div>
        <div>
          <h3 className="mt-2 text-lg font-medium leading-6 text-gray-900">
            {schema.kind.value}
          </h3>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Attributes and details
          </p>
        </div>
        <div className="mt-5 border-t border-gray-200">
          <dl className="sm:divide-y sm:divide-gray-200">
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Name</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {schema.name.value}
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Kind</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {schema.kind.value}
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">
                Default filter
              </dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {schema.default_filter?.value}
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Description</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {schema.description?.value}
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Attributes</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                <ul
                  className="divide-y divide-gray-200 rounded-md border border-gray-200"
                >
                  {schema.attributes?.map((attribute) => (
                    <li className="flex items-center justify-between py-3 pl-3 pr-4 text-sm">
                      <div className="flex w-0 flex-1 items-center">
                        <span className="ml-2 w-0 flex-1 truncate">
                          {attribute?.name.value}
                        </span>
                      </div>
                      <div className="ml-4 flex-shrink-0 flex space-x-2">
                        {(attribute?.optional.value === false ||
                          attribute?.unique.value) && (
                          <ShieldCheckIcon className="w-4 h-4" />
                        )}
                        {(attribute?.unique.value === true ||
                          attribute?.unique.value) && (
                          <StarIcon className="w-4 h-4" />
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Query</dt>
              <dd
                className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 whitespace-pre-wrap"
                dangerouslySetInnerHTML={{ __html: queryString }}
              ></dd>
            </div>
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5">
              <dt className="text-sm font-medium text-gray-500">Rows ({objectRows.length})</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                <ul
                  className="divide-y divide-gray-200 rounded-md border border-gray-200"
                >
                  {objectRows.map((row: any) => {
                    if (row?.[displayAttribute]) {
                      return (
                        <li className="flex items-center justify-between py-3 pl-3 pr-4 text-sm">
                          <div className="flex w-0 flex-1 items-center">
                            <span className="ml-2 w-0 flex-1 truncate">
                              {row?.[displayAttribute].value}
                            </span>
                          </div>
                        </li>
                      );
                    } else {
                      return null;
                    }
                  })}
                </ul>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
