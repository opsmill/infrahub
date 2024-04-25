import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import { LockClosedIcon, PencilIcon, RectangleGroupIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
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
  TASK_TAB,
  TASK_TARGET,
} from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { constructPath } from "../../utils/fetch";
import { ObjectAttributeValue } from "../../utils/getObjectItemDisplayValue";
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
import Content from "../layout/content";
import { usePermission } from "../../hooks/usePermission";
import { ButtonWithTooltip } from "../../components/buttons/button-with-tooltip";
import { ButtonWithTooltip as ButtonWithTooltip2 } from "../../components/buttons/button-primitive";

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
  const permission = usePermission();
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
    // Includes the task tab only for specific objects
    schema?.inherit_from?.includes(TASK_TARGET) && {
      label: "Tasks",
      name: TASK_TAB,
      count: data[TASK_OBJECT]?.count ?? 0,
      onClick: () => {
        setQspTab(TASK_TAB);
        setQspTaskId(undefined);
      },
    },
  ].filter(Boolean);

  if (!objectDetailsData) {
    return null;
  }

  return (
    <Content>
      {!hideHeaders && (
        <div className="bg-custom-white">
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

          <div className="px-4">{schemaData?.description}</div>

          <Tabs
            tabs={tabs}
            rightItems={
              <>
                {schemaData.kind === ARTIFACT_DEFINITION_OBJECT && <Generate />}

                <ButtonWithTooltip
                  disabled={!permission.write.allow}
                  tooltipEnabled={!permission.write.allow}
                  tooltipContent={permission.write.message ?? undefined}
                  onClick={() => setShowEditDrawer(true)}
                  className="mr-4">
                  Edit
                  <PencilIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                </ButtonWithTooltip>

                {!schemaData.kind?.match(/Core.*Group/g)?.length && ( // Hide group buttons on group list view
                  <ButtonWithTooltip
                    disabled={!permission.write.allow}
                    tooltipEnabled={!permission.write.allow}
                    tooltipContent={permission.write.message ?? undefined}
                    onClick={() => setShowAddToGroupDrawer(true)}
                    className="mr-4">
                    Manage groups
                    <RectangleGroupIcon className="ml-2 h-4 w-4" aria-hidden="true" />
                  </ButtonWithTooltip>
                )}
              </>
            }
          />
        </div>
      )}

      {!qspTab && (
        <dl className="bg-custom-white divide-y">
          <ObjectAttributeRow name="ID" value={objectDetailsData.id} enableCopyToClipboard />
          {attributes.map((attribute) => {
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
                    <ObjectAttributeValue
                      attributeSchema={attribute}
                      attributeValue={objectDetailsData[attribute.name]}
                    />

                    {objectDetailsData[attribute.name] && (
                      <MetaDetailsTooltip
                        updatedAt={objectDetailsData[attribute.name].updated_at}
                        source={objectDetailsData[attribute.name].source}
                        owner={objectDetailsData[attribute.name].owner}
                        isFromProfile={objectDetailsData[attribute.name].is_from_profile}
                        isProtected={objectDetailsData[attribute.name].is_protected}
                        isInherited={objectDetailsData[attribute.name].is_inherited}
                        header={
                          <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b">
                            <div className="font-semibold">{attribute.label}</div>
                            <ButtonWithTooltip2
                              disabled={!permission.write.allow}
                              tooltipEnabled={!permission.write.allow}
                              tooltipContent={permission.write.message ?? undefined}
                              onClick={() => {
                                setMetaEditFieldDetails({
                                  type: "attribute",
                                  attributeOrRelationshipName: attribute.name,
                                  label: attribute.label || attribute.name,
                                });
                                setShowMetaEditModal(true);
                              }}
                              variant="ghost"
                              size="icon"
                              data-testid="edit-metadata-button"
                              data-cy="metadata-edit-button">
                              <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                            </ButtonWithTooltip2>
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
      )}

      {qspTab && qspTab !== TASK_TAB && (
        <RelationshipsDetails
          parentNode={objectDetailsData}
          parentSchema={schemaData}
          refetchObjectDetails={refetch}
          ref={refetchRef}
        />
      )}

      {qspTab && qspTab === TASK_TAB && !qspTaskId && (
        <TaskItems ref={refetchRef} hideRelatedNode />
      )}

      {qspTab && qspTab === TASK_TAB && qspTaskId && (
        <div>
          <div className="flex bg-custom-white text-sm">
            <Link
              to={constructPath(pathname, [
                { name: QSP.TAB, value: TASK_TAB },
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
            <div className="flex items-start">
              <div className="flex-grow flex items-center flex-wrap overflow-hidden">
                <span className="font-semibold text-gray-900 truncate">{schemaData.label}</span>

                <ChevronRightIcon
                  className="w-4 h-4 flex-shrink-0 mx-2 text-gray-400"
                  aria-hidden="true"
                />

                <span className="flex-grow text-gray-500 overflow-hidden break-words line-clamp-3">
                  {objectDetailsData.display_label}
                </span>
              </div>

              <div className="flex items-center ml-3">
                <Icon icon="mdi:layers-triple" />
                <span className="ml-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</span>
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
    </Content>
  );
}
