import { ChevronRightIcon } from "@heroicons/react/20/solid";
import {
  CheckIcon,
  EyeSlashIcon,
  LockClosedIcon,
  PencilIcon,
  PencilSquareIcon,
  XMarkIcon
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import SlideOver from "../../components/slide-over";
import { branchState } from "../../state/atoms/branch.atom";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { iSchemaKindNameMap, schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { timeState } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import getObjectDetails from "../../utils/objectDetails";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit.component";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";

export default function ObjectItemDetails() {
  let { objectname, objectid } = useParams();
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [selectedTab, setSelectedTab] = useState<string | undefined>();
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const [showMetaEditModal, setShowMetaEditModal] = useState(false);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useState<{
    type: "attribute" | "relationship",
  attributeOrRelationshipName: any;
  }>();

  const [objectDetails, setObjectDetails] = useState<any | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  const navigate = useNavigate();
  const { search } = useLocation();

  const navigateToObjectEditPage = () => {
    navigate(`/objects/${objectname}/${objectid}/edit/${search}`);
  };

  interface iRelationDetailsProps {
    relationship: iNodeSchema["relationships"];
    row: any;
  }

  const getObjectDetailsUrl = (row: {__typename: string}, schemaKindName: iSchemaKindNameMap, schema: iNodeSchema, relatedNodeId: string) :string => {
    const regex = /^Related/; // starts with Related
    const peerKind: string = row.__typename.replace(regex, "");
    const peerName = schemaKindName[peerKind];
    const url = `/objects/${peerName}/${relatedNodeId}`;
    return url;
  };

  const RelationshipDetails = (props: iRelationDetailsProps) => {
    const { row, relationship: relationships } = props;
    const relationship = relationships![0];

    if(!row || !row[relationship.name] || row[relationship.name]._relation__is_visible === false) {
      return null;
    }

    return <>
      <div
        className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
        key={relationship.name}
      >
        <dt className="text-sm font-medium text-gray-500 flex items-center">
          {relationship.label}
        </dt>
        {row[relationship.name] && (
          <>
            {relationship.cardinality === "one" && (
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline flex items-center">
                <Link
                  to={getObjectDetailsUrl(row[relationship.name], schemaKindName, schema, row[relationship.name].id)}
                >
                  {row[relationship.name].display_label}
                </Link>

                {row[relationship.name] && (
                  <MetaDetailsTooltip
                    header={(<div className="flex justify-between w-full py-4">
                      <div className="font-semibold">{relationship.label}</div>
                      <div className="cursor-pointer" onClick={() => {
                        setMetaEditFieldDetails({
                          type: "relationship",
                          attributeOrRelationshipName: relationship.name,
                        });
                        setShowMetaEditModal(true);
                      }}>
                        <PencilSquareIcon className="w-5 h-5 text-blue-500" />
                      </div>
                    </div>
                    )}
                    items={[
                      {
                        label: "Updated at",
                        value: row[relationship.name]._updated_at,
                        type: "date",
                      },
                      {
                        label: "Update time",
                        value: `${new Date(row[relationship.name]._updated_at).toLocaleDateString()} ${new Date(row[relationship.name]._updated_at).toLocaleTimeString()}`,
                        type: "text",
                      },
                      {
                        label: "Source",
                        value: row[relationship.name]._relation__source,
                        type: "link"
                      },
                      {
                        label: "Owner",
                        value: row[relationship.name]._relation__owner,
                        type: "link"
                      },
                      {
                        label: "Is protected",
                        value: row[relationship.name]._relation__is_protected ? "True" : "False",
                        type: "text"
                      },
                    ]} />
                )}

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
                      to={getObjectDetailsUrl(item, schemaKindName, schema, item.id)}
                    >
                      {item.display_label}
                    </Link>

                    {item && (
                      <MetaDetailsTooltip items={[
                        {
                          label: "Updated at",
                          value: item._updated_at,
                          type: "date",
                        },
                        {
                          label: "Update time",
                          value: `${new Date(item._updated_at).toLocaleDateString()} ${new Date(item._updated_at).toLocaleTimeString()}`,
                          type: "text",
                        },
                        {
                          label: "Source",
                          value: item._relation__source,
                          type: "link"
                        },
                        {
                          label: "Owner",
                          value: item._relation__owner,
                          type: "link"
                        },
                        {
                          label: "Is protected",
                          value: item._relation__is_protected ? "True" : "False",
                          type: "text"
                        },
                      ]} />
                    )}

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
    </>;
  };

  const fetchObjectDetails = useCallback(async () => {
    setHasError(false);
    setIsLoading(true);
    setObjectDetails(undefined);
    setSelectedTab(undefined);
    try {
      const data = await getObjectDetails(schema, objectid!);
      setObjectDetails(data);
    } catch(err) {
      setHasError(true);
    }
    setIsLoading(false);
  }, [objectid, schema]);

  useEffect(() => {
    if(schema) {
      fetchObjectDetails();
    }
  }, [fetchObjectDetails, schema, date, branch]);

  if (hasError) {
    return <ErrorScreen />;
  }

  if (isLoading || !schema) {
    return <LoadingScreen />;
  }

  if (!objectDetails) {
    return <NoDataFound />;
  }

  const row = objectDetails;

  return (
    <div className="bg-white flex-1 overflow-auto">
      <div className="px-4 py-5 sm:px-6 flex items-center">
        <div
          onClick={() => navigate(`/objects/${objectname}/${search}`)}
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
        >
          {schema.kind}
        </div>
        <ChevronRightIcon
          className="h-5 w-5 mt-1 mx-2 flex-shrink-0 text-gray-400"
          aria-hidden="true"
        />
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{row.display_label}</p>
      </div>
      <div className="flex items-center">
        <div className="flex-1">
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
        <button
          // onClick={navigateToObjectEditPage}
          onClick={() => {
            setShowEditDrawer(true);
            return false;
            navigateToObjectEditPage();
          }}
          type="button"
          className="mr-3 inline-flex items-center gap-x-1.5 rounded-md py-1.5 px-2.5 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 bg-white  text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
        >
          Edit
          <PencilIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      {!selectedTab && (
        <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-gray-200">
            <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
              <dt className="text-sm font-medium text-gray-500 flex items-center">ID</dt>
              <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                {row.id}
              </dd>
            </div>
            {schema.attributes?.map((attribute) => {
              if (!row[attribute.name] || !row[attribute.name].is_visible) {
                return null;
              }

              return (
                <div
                  className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
                  key={attribute.name}
                >
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    {attribute.label}
                  </dt>

                  <div className="flex items-center">
                    <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                      {(row[attribute.name]?.value !== false && row[attribute.name].value) ? row[attribute.name].value : "-"}
                      {row[attribute.name]?.value === true && (<CheckIcon className="h-4 w-4" />)}
                      {row[attribute.name]?.value === false && (<XMarkIcon className="h-4 w-4" />)}
                    </dd>

                    {row[attribute.name] && (
                      <MetaDetailsTooltip
                        header={(<div className="flex justify-between w-full py-4">
                          <div className="font-semibold">{attribute.label}</div>
                          <div className="cursor-pointer" onClick={() => {
                            setMetaEditFieldDetails({
                              type: "attribute",
                              attributeOrRelationshipName: attribute.name,
                            });
                            setShowMetaEditModal(true);
                          }}>
                            <PencilSquareIcon className="w-5 h-5 text-blue-500" />
                          </div>
                        </div>
                        )}
                        items={[
                          {
                            label: "Updated at",
                            value: row[attribute.name].updated_at,
                            type: "date",
                          },
                          {
                            label: "Update time",
                            value: `${new Date(row[attribute.name].updated_at).toLocaleDateString()} ${new Date(row[attribute.name].updated_at).toLocaleTimeString()}`,
                            type: "text",
                          },
                          {
                            label: "Source",
                            value: row[attribute.name].source,
                            type: "link"
                          },
                          {
                            label: "Owner",
                            value: row[attribute.name].owner,
                            type: "link"
                          },
                          {
                            label: "Is protected",
                            value: row[attribute.name].is_protected ? "True" : "False",
                            type: "text"
                          },
                          {
                            label: "Is inherited",
                            value: row[attribute.name].is_inherited ? "True" : "False",
                            type: "text"
                          },
                        ]} />
                    )}

                    {row[attribute.name].is_protected && (
                      <LockClosedIcon className="h-5 w-5 ml-2" />
                    )}
                  </div>
                </div>
              );
            })}

            {schema.relationships
            ?.filter((relationship) => relationship.kind === "Attribute").map(relationship => <RelationshipDetails key={relationship.name} relationship={[relationship]} row={row} />)}



          </dl>
        </div>
      )}
      {selectedTab && (
        <div className="border-t border-gray-200 px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-gray-200">
            {schema.relationships
            ?.filter((relationship) => relationship.name === selectedTab)
            .map((relationship) => (
              <RelationshipDetails key={relationship.name} relationship={[relationship]} row={row} />
            ))}
          </dl>
        </div>
      )}
      <SlideOver title="Edit" subtitle="Update Account details by filling in the information below" open={showEditDrawer} setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent closeDrawer={() => {
          setShowEditDrawer(false);
        }}  onUpdateComplete={() => {
          fetchObjectDetails();
        }} objectid={objectid!} objectname={objectname!} />
      </SlideOver>
      <SlideOver title={`${metaEditFieldDetails?.attributeOrRelationshipName} > Meta-details`} subtitle="Update meta details" open={showMetaEditModal} setOpen={setShowMetaEditModal}>
        <ObjectItemMetaEdit closeDrawer={() => {
          setShowMetaEditModal(false);
        }}  onUpdateComplete={() => {
          setShowMetaEditModal(false);
          fetchObjectDetails();
        }} schemaList={schemaList} schema={schema} attributeOrRelationshipName={metaEditFieldDetails?.attributeOrRelationshipName} type={metaEditFieldDetails?.type!} row={objectDetails}  />
      </SlideOver>
    </div>
  );
}
