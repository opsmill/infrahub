import { useAtom } from "jotai";
import { gql } from "@apollo/client";
import { useEffect, useState, Fragment } from "react";
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
import {
  CheckIcon,
  InformationCircleIcon,
  LockClosedIcon,
  EyeSlashIcon,
} from "@heroicons/react/24/outline";
import { classNames } from "../../App";
import { formatDistance } from "date-fns";
import { Popover, Transition } from "@headlessui/react";

declare var Handlebars: any;

const template = Handlebars.compile(`query {{kind.value}} {
        {{name}} (ids: ["{{objectid}}"]) {
            id
            {{#each attributes}}
            {{this.name}} {
                value
                updated_at
                is_protected
                is_visible
                source {
                  id
                  display_label
                  __typename
                }
                owner {
                  id
                  display_label
                  __typename
                }
            }
            {{/each}}
            {{#each relationships}}
            {{this.name}} {
                id
                display_label
                _relation__is_visible
                _relation__is_protected
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
  const [selectedTab, setSelectedTab] = useState<string | undefined>();

  const [objectRows, setObjectRows] = useState<any[] | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const navigate = useNavigate();

  const navigateToObjectDetailsPage = (obj: any) => {
    navigate(`/objects/${schemaKindName[obj.__typename]}/${obj.id}`);
  };

  useEffect(() => {
    if (schema) {
      setHasError(false);
      setIsLoading(true);
      setObjectRows(undefined);
      setSelectedTab(undefined);
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

  if ((isLoading && !objectRows) || !objectRows?.length || !row || !schema) {
    return <LoadingScreen />;
  }

  if (objectRows && objectRows.length === 0) {
    return <NoDataFound />;
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
      <div>
        <div>
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8 px-4" aria-label="Tabs">
              <div
                onClick={() => setSelectedTab(undefined)}
                className={classNames(
                  !selectedTab
                    ? "border-indigo-500 text-indigo-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
                  "whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium cursor-pointer"
                )}
              >
                {schema.label}
              </div>
              {schema.relationships
                ?.filter((relationship) => relationship.kind !== "Attribute")
                .map((relationship, index) => (
                  <div
                    key={relationship.name}
                    onClick={() => setSelectedTab(relationship.name)}
                    className={classNames(
                      selectedTab && selectedTab === relationship.name
                        ? "border-indigo-500 text-indigo-600"
                        : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
                      "whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium cursor-pointer"
                    )}
                  >
                    {relationship.label}
                  </div>
                ))}
            </nav>
          </div>
        </div>
      </div>
      {!selectedTab && (
        <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-gray-200">
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500">ID</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {row.id}
              </dd>
            </div>
            {schema.attributes?.map((attribute) => {
              if (!row[attribute.name]) {
                return null;
              }
              return (
                <div
                  className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
                  key={attribute.name}
                >
                  <dt className="text-sm font-medium text-gray-500">
                    {attribute.label}
                  </dt>

                  <div className="flex items-center">
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                      {row[attribute.name].value || "-"}
                      {row[attribute.name].value === true && (
                        <CheckIcon className="h-4 w-4" />
                      )}
                    </dd>

                    {row[attribute.name] &&
                      row[attribute.name].source &&
                      row[attribute.name].owner &&
                      row[attribute.name].updated_at && (
                        <Popover className="relative mt-1.5 ml-2">
                          <Popover.Button>
                            <InformationCircleIcon className="w-5 h-5" />
                          </Popover.Button>
                          <Transition
                            as={Fragment}
                            enter="transition ease-out duration-200"
                            enterFrom="opacity-0 translate-y-1"
                            enterTo="opacity-100 translate-y-0"
                            leave="transition ease-in duration-150"
                            leaveFrom="opacity-100 translate-y-0"
                            leaveTo="opacity-0 translate-y-1"
                          >
                            <Popover.Panel className="absolute z-10 bg-white rounded-lg border shadow-xl">
                              <div className="w-80 text-sm divide-y px-4">
                                <div className="flex justify-between w-full py-4">
                                  <div>Updated at: </div>

                                  <div>
                                    {formatDistance(
                                      new Date(row[attribute.name].updated_at),
                                      new Date(),
                                      { addSuffix: true }
                                    )}
                                  </div>
                                </div>
                                <div className="flex justify-between w-full py-4">
                                  <div>Source: </div>
                                  <div
                                    className="underline cursor-pointer"
                                    onClick={() =>
                                      navigateToObjectDetailsPage(
                                        row[attribute.name].source
                                      )
                                    }
                                  >
                                    {row[attribute.name].source.display_label}
                                  </div>
                                </div>
                                <div className="flex justify-between w-full py-4">
                                  <div>Owner: </div>
                                  <div
                                    className="underline cursor-pointer"
                                    onClick={() =>
                                      navigateToObjectDetailsPage(
                                        row[attribute.name].owner
                                      )
                                    }
                                  >
                                    {row[attribute.name].owner.display_label}
                                  </div>
                                </div>
                              </div>
                            </Popover.Panel>
                          </Transition>
                        </Popover>
                      )}

                    {row[attribute.name].is_protected && (
                      <LockClosedIcon className="h-5 w-5 ml-2" />
                    )}

                    {row[attribute.name].is_visible === false && (
                      <EyeSlashIcon className="h-5 w-5 ml-2" />
                    )}
                  </div>
                </div>
              );
            })}
            {schema.relationships
              ?.filter((relationship) => relationship.kind === "Attribute")
              .map((relationship) => (
                <div
                  className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
                  key={relationship.name}
                >
                  <dt className="text-sm font-medium text-gray-500">
                    {relationship.label}
                  </dt>
                  {row[relationship.name] && (
                    <>
                      {relationship.cardinality === "one" && (
                        <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline flex items-center">
                          <Link
                            to={`/objects/${
                              schemaKindName[relationship.peer]
                            }/${row[relationship.name].id}`}
                          >
                            {row[relationship.name].id}
                          </Link>
                          {row[relationship.name]._relation__is_protected && (
                            <LockClosedIcon className="h-5 w-5 ml-2" />
                          )}

                          {row[relationship.name]._relation__is_visible ===
                            false && <EyeSlashIcon className="h-5 w-5 ml-2" />}
                        </dd>
                      )}
                      {relationship.cardinality === "many" && (
                        <div className="sm:col-span-2 space-y-4">
                          {row[relationship.name].map((item: any) => (
                            <dd
                              className="mt-1 text-sm text-gray-900 sm:mt-0 underline flex items-center"
                              key={item.id}
                            >
                              <Link
                                to={`/objects/${
                                  schemaKindName[relationship.peer]
                                }/${item.id}`}
                              >
                                {item.id}
                              </Link>
                              {item._relation__is_protected && (
                                <LockClosedIcon className="h-5 w-5 ml-2" />
                              )}

                              {item._relation__is_visible === false && (
                                <EyeSlashIcon className="h-5 w-5 ml-2" />
                              )}
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
      )}
      {selectedTab && (
        <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-gray-200">
            {schema.relationships
              ?.filter((relationship) => relationship.name === selectedTab)
              .map((relationship) => (
                <div
                  className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
                  key={relationship.name}
                >
                  <dt className="text-sm font-medium text-gray-500">
                    {relationship.label}
                  </dt>
                  {row[relationship.name] && (
                    <>
                      {relationship.cardinality === "one" && (
                        <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline">
                          <Link
                            to={`/objects/${
                              schemaKindName[relationship.peer]
                            }/${row[relationship.name].id}`}
                          >
                            {row[relationship.name].display_label}
                          </Link>
                        </dd>
                      )}
                      {relationship.cardinality === "many" && (
                        <div className="sm:col-span-2 space-y-4">
                          {row[relationship.name].map((item: any) => (
                            <dd
                              className="mt-1 text-sm text-gray-900 sm:mt-0 underline"
                              key={item.id}
                            >
                              <Link
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
      )}
    </div>
  );
}
