import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import {
  LockClosedIcon,
  PencilIcon,
  PencilSquareIcon,
  RectangleGroupIcon,
} from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { BUTTON_TYPES, Button } from "../../components/buttons/button";
import { Retry } from "../../components/buttons/retry";
import MetaDetailsTooltip from "../../components/display/meta-details-tooltips";
import SlideOver from "../../components/display/slide-over";
import { Tabs } from "../../components/tabs";
import { Link } from "../../components/utils/link";
import {
  ARTIFACT_DEFINITION_OBJECT,
  DEFAULT_BRANCH_NAME,
  MENU_EXCLUDELIST,
  TASK_OBJECT,
} from "../../config/constants";
import { QSP } from "../../config/qsp";
import { useAuth } from "../../hooks/useAuth";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import {
  getObjectAttributes,
  getObjectRelationships,
  getObjectTabs,
  getSchemaObjectColumns,
  getTabs,
} from "../../utils/getSchemaObjectColumns";
import { Generate } from "../artifacts/generate";
import ErrorScreen from "../error-screen/error-screen";
import AddObjectToGroup from "../groups/add-object-to-group";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";
import { TaskItemDetails } from "../tasks/task-item-details";
import { TaskItems } from "../tasks/task-items";
import { ObjectAttributeRow } from "./object-attribute-row";
import RelationshipDetails from "./relationship-details-paginated";
import { RelationshipsDetails } from "./relationships-details-paginated";

export default function ObjectItemDetails(props: any) {
  const { objectname: objectnameFromProps, objectid: objectidFromProps, hideHeaders } = props;

  const location = useLocation();
  const { pathname } = location;

  const { objectname: objectnameFromParams, objectid: objectidFromParams } = useParams();
  const objectname = objectnameFromProps || objectnameFromParams;
  const objectid = objectidFromProps || objectidFromParams;

  const [qspTab, setQspTab] = useQueryParam(QSP.TAB, StringParam);
  const [qspTaskId, setQspTaskId] = useQueryParam(QSP.TASK_ID, StringParam);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const [showAddToGroupDrawer, setShowAddToGroupDrawer] = useState(false);
  const auth = useAuth();
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);
  const branch = useAtomValue(currentBranchAtom);
  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericList] = useAtom(genericsState);
  const schema = schemaList.find((s) => s.kind === objectname);
  const generic = genericList.find((s) => s.kind === objectname);
  const navigate = useNavigate();

  const refetchRef = useRef(null);

  const schemaData = generic || schema;

  if ((schemaList?.length || genericList?.length) && !schemaData) {
    // If there is no schema nor generics, go to home page
    navigate("/");
    return null;
  }

  if (schemaData && MENU_EXCLUDELIST.includes(schemaData.kind)) {
    navigate("/");
    return null;
  }

  const attributes = getObjectAttributes(schemaData);
  const relationships = getObjectRelationships(schemaData);
  const columns = getSchemaObjectColumns(schemaData);
  const relationshipsTabs = getTabs(schemaData);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        kind: schemaData.kind,
        taskKind: TASK_OBJECT,
        columns,
        relationshipsTabs,
        objectid,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, error, data, refetch } = useQuery(query, {
    skip: !schemaData,
    notifyOnNetworkStatusChange: true,
  });

  // TODO: refactor to not need the ref to refetch child query
  const handleRefetch = () => {
    refetch();
    if (refetchRef?.current?.refetch) {
      refetchRef?.current?.refetch();
    }
  };

  const objectDetailsData = schemaData && data && data[schemaData?.kind]?.edges[0]?.node;

  useTitle(
    objectDetailsData?.display_label
      ? `${objectDetailsData?.display_label} details`
      : `${schemaKindName[objectname]} details`
  );

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  if (!objectDetailsData && (loading || !schemaData)) {
    return <LoadingScreen />;
  }

  if (!objectDetailsData) {
    return (
      <div className="flex column justify-center">
        <NoDataFound message="No item found for that id." />
      </div>
    );
  }

  const tabs = [
    {
      label: schemaData?.label,
      name: schemaData?.label,
    },
    ...getObjectTabs(relationshipsTabs, objectDetailsData),
    {
      label: "Tasks",
      name: "tasks",
      count: data[TASK_OBJECT]?.count ?? 0,
      onClick: () => {
        setQspTab("tasks");
        setQspTaskId(undefined);
      },
    },
  ];

  if (!objectDetailsData) {
    return null;
  }

  return (
    <div className="flex-1 overflow-auto flex flex-col">
      <div className="bg-custom-white">
        {!hideHeaders && (
          <>
            <div className="px-4 py-5 flex items-center">
              <Link to={constructPath(`/objects/${objectname}`)}>
                <h1 className="text-md font-semibold text-gray-900 mr-2">{schemaData.name}</h1>
              </Link>

              <ChevronRightIcon
                className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
                aria-hidden="true"
              />

              <p className="max-w-2xl  text-gray-500">{objectDetailsData.display_label}</p>

              <div className="ml-2">
                <Retry isLoading={loading} onClick={handleRefetch} />
              </div>
            </div>

            <div className="px-4 ">{schemaData?.description}</div>

            <Tabs
              tabs={tabs}
              rightItems={
                <>
                  {schemaData.kind === ARTIFACT_DEFINITION_OBJECT && <Generate />}

                  <Button
                    disabled={!auth?.permissions?.write}
                    onClick={() => setShowEditDrawer(true)}
                    className="mr-4">
                    Edit
                    <PencilIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                  </Button>

                  {!schemaData.kind?.match(/Core.*Group/g)?.length && ( // Hide group buttons on group list view
                    <Button
                      disabled={!auth?.permissions?.write}
                      onClick={() => setShowAddToGroupDrawer(true)}
                      className="mr-4">
                      Manage groups
                      <RectangleGroupIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                    </Button>
                  )}
                </>
              }
            />
          </>
        )}

        {!qspTab && (
          <div className="px-4 py-5 sm:p-0 flex-1 overflow-auto">
            <dl className="sm:divide-y sm:divide-gray-200">
              <ObjectAttributeRow name="ID" value={objectDetailsData.id} />
              {attributes?.map((attribute) => {
                if (
                  !objectDetailsData[attribute.name] ||
                  !objectDetailsData[attribute.name].is_visible
                ) {
                  return null;
                }

                return (
                  <ObjectAttributeRow
                    key={attribute.name}
                    name={attribute.label as string}
                    value={
                      <>
                        {getObjectItemDisplayValue(objectDetailsData, attribute, schemaKindName)}

                        {objectDetailsData[attribute.name] && (
                          <MetaDetailsTooltip
                            items={[
                              {
                                label: "Updated at",
                                value: objectDetailsData[attribute.name].updated_at,
                                type: "date",
                              },
                              {
                                label: "Update time",
                                value: `${new Date(
                                  objectDetailsData[attribute.name].updated_at
                                ).toLocaleDateString()} ${new Date(
                                  objectDetailsData[attribute.name].updated_at
                                ).toLocaleTimeString()}`,
                                type: "text",
                              },
                              {
                                label: "Source",
                                value: objectDetailsData[attribute.name].source,
                                type: "link",
                              },
                              {
                                label: "Owner",
                                value: objectDetailsData[attribute.name].owner,
                                type: "link",
                              },
                              {
                                label: "Is protected",
                                value: objectDetailsData[attribute.name].is_protected
                                  ? "True"
                                  : "False",
                                type: "text",
                              },
                              {
                                label: "Is inherited",
                                value: objectDetailsData[attribute.name].is_inherited
                                  ? "True"
                                  : "False",
                                type: "text",
                              },
                            ]}
                            header={
                              <div className="flex justify-between items-center w-full p-4">
                                <div className="font-semibold">{attribute.label}</div>
                                <Button
                                  buttonType={BUTTON_TYPES.INVISIBLE}
                                  disabled={!auth?.permissions?.write}
                                  onClick={() => {
                                    setMetaEditFieldDetails({
                                      type: "attribute",
                                      attributeOrRelationshipName: attribute.name,
                                      label: attribute.label || attribute.name,
                                    });
                                    setShowMetaEditModal(true);
                                  }}
                                  data-testid="edit-metadata-button"
                                  data-cy="metadata-edit-button">
                                  <PencilSquareIcon className="w-4 h-4 text-custom-blue-500" />
                                </Button>
                              </div>
                            }
                          />
                        )}

                        {objectDetailsData[attribute.name].is_protected && (
                          <LockClosedIcon className="w-4 h-4" />
                        )}
                      </>
                    }
                  />
                );
              })}

              {relationships?.map((relationship: any) => {
                const relationshipSchema = schemaData?.relationships?.find(
                  (relation) => relation?.name === relationship?.name
                );

                const relationshipData = relationship?.paginated
                  ? objectDetailsData[relationship.name]?.edges
                  : objectDetailsData[relationship.name];

                return (
                  <RelationshipDetails
                    parentNode={objectDetailsData}
                    mode="DESCRIPTION-LIST"
                    parentSchema={schemaData}
                    key={relationship.name}
                    relationshipsData={relationshipData}
                    relationshipSchema={relationshipSchema}
                  />
                );
              })}
            </dl>
          </div>
        )}
      </div>

      {qspTab && qspTab !== "tasks" && (
        <RelationshipsDetails
          parentNode={objectDetailsData}
          parentSchema={schemaData}
          refetchObjectDetails={refetch}
          ref={refetchRef}
        />
      )}

      {qspTab && qspTab === "tasks" && !qspTaskId && <TaskItems ref={refetchRef} />}

      {qspTab && qspTab === "tasks" && qspTaskId && (
        <div>
          <div className="flex bg-custom-white text-sm">
            <Link
              to={constructPath(pathname, [
                { name: QSP.TAB, value: "tasks" },
                { name: QSP.TASK_ID, exclude: true },
              ])}
              className="flex items-center p-2 ">
              <Icon icon={"mdi:chevron-left"} />
              All tasks
            </Link>
          </div>

          <TaskItemDetails ref={refetchRef} />
        </div>
      )}

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex">
              <div className="flex items-center overflow-x-hidden flex-grow">
                <div className="font-semibold text-gray-900">{schemaData.label}</div>

                <ChevronRightIcon
                  className="w-4 h-4 flex-shrink-0 mx-2 text-gray-400"
                  aria-hidden="true"
                />

                <p className="text-gray-500 text-ellipsis overflow-hidden">
                  {objectDetailsData.display_label}
                </p>
              </div>

              <div className="flex items-center ml-2">
                <Icon icon="mdi:layers-triple" />
                <div className="ml-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="">{schemaData?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schemaData.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {objectDetailsData.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditDrawer(false)}
          onUpdateComplete={() => refetch()}
          objectid={objectid!}
          objectname={objectname!}
        />
      </SlideOver>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <div className="flex items-center">
                <div className="text-base font-semibold leading-6 text-gray-900">
                  {schemaData.label}
                </div>
                <ChevronRightIcon
                  className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
                  aria-hidden="true"
                />
                <p className="max-w-2xl  text-gray-500">{objectDetailsData.display_label}</p>
              </div>

              <div className="flex-1"></div>

              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="">{schemaData?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schemaData.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-custom-blue-500 ring-1 ring-inset ring-custom-blue-500/10">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-custom-blue-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {objectDetailsData.id}
            </div>
          </div>
        }
        open={showAddToGroupDrawer}
        setOpen={setShowAddToGroupDrawer}>
        <AddObjectToGroup
          closeDrawer={() => setShowAddToGroupDrawer(false)}
          onUpdateComplete={() => refetch()}
        />
      </SlideOver>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">{metaEditFieldDetails?.label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <div className="text-gray-500">Metadata</div>
          </div>
        }
        open={showMetaEditModal}
        setOpen={setShowMetaEditModal}>
        <ObjectItemMetaEdit
          closeDrawer={() => setShowMetaEditModal(false)}
          onUpdateComplete={() => refetch()}
          attributeOrRelationshipToEdit={
            objectDetailsData[metaEditFieldDetails?.attributeOrRelationshipName]?.properties ||
            objectDetailsData[metaEditFieldDetails?.attributeOrRelationshipName]
          }
          schema={schemaData}
          attributeOrRelationshipName={metaEditFieldDetails?.attributeOrRelationshipName}
          type={metaEditFieldDetails?.type!}
          row={objectDetailsData}
        />
      </SlideOver>
    </div>
  );
}
