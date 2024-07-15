import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/components/display/meta-details-tooltips";
import SlideOver from "@/components/display/slide-over";
import { Tabs } from "@/components/tabs";
import { Link } from "@/components/ui/link";
import {
  ARTIFACT_DEFINITION_OBJECT,
  DEFAULT_BRANCH_NAME,
  MENU_EXCLUDELIST,
  TASK_TAB,
  TASK_TARGET,
} from "@/config/constants";
import { QSP } from "@/config/qsp";
import { usePermission } from "@/hooks/usePermission";
import { useTitle } from "@/hooks/useTitle";
import { Generate } from "@/screens/artifacts/generate";
import NoDataFound from "@/screens/errors/no-data-found";
import ObjectItemEditComponent from "@/screens/object-item-edit/object-item-edit-paginated";
import ObjectItemMetaEdit from "@/screens/object-item-meta-edit/object-item-meta-edit";
import { TaskItemDetails } from "@/screens/tasks/task-item-details";
import { TaskItems } from "@/screens/tasks/task-items";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { showMetaEditState } from "@/state/atoms/metaEditFieldDetails.atom";
import { genericsState, IModelSchema, schemaState } from "@/state/atoms/schema.atom";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "@/state/atoms/showMetaEdit.atom copy";
import { constructPath } from "@/utils/fetch";
import { ObjectAttributeValue } from "@/utils/getObjectItemDisplayValue";
import {
  getObjectAttributes,
  getObjectRelationships,
  getObjectTabs,
  getTabs,
} from "@/utils/getSchemaObjectColumns";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useRef, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { ObjectAttributeRow } from "./object-attribute-row";
import RelationshipDetails from "./relationship-details-paginated";
import { RelationshipsDetails } from "./relationships-details-paginated";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { GroupsManagerTriggerButton } from "@/screens/groups/groups-manager-trigger-button";

type ObjectDetailsProps = {
  schema: IModelSchema;
  objectDetailsData: any;
  taskData?: Object;
  hideHeaders?: boolean;
};
export default function ObjectItemDetails({
  schema,
  objectDetailsData,
  taskData,
  hideHeaders,
}: ObjectDetailsProps) {
  const location = useLocation();
  const { pathname } = location;

  const objectname = schema.kind;
  const objectid = objectDetailsData.id;

  const [qspTab, setQspTab] = useQueryParam(QSP.TAB, StringParam);
  const [qspTaskId, setQspTaskId] = useQueryParam(QSP.TASK_ID, StringParam);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const permission = usePermission();
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);
  const branch = useAtomValue(currentBranchAtom);
  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericList] = useAtom(genericsState);

  const refetchRef = useRef(null);

  if ((schemaList?.length || genericList?.length) && !schema) {
    // If there is no schema nor generics, go to home page
    return <Navigate to="/" />;
  }

  if (schema && MENU_EXCLUDELIST.includes(schema.kind!)) {
    return <Navigate to="/" />;
  }

  const attributes = getObjectAttributes({ schema: schema });
  const relationships = getObjectRelationships({ schema: schema });
  const relationshipsTabs = getTabs(schema);

  useTitle(
    objectDetailsData?.display_label
      ? `${objectDetailsData?.display_label} details`
      : `${schemaKindName[objectname]} details`
  );

  if (!objectDetailsData) {
    return (
      <div className="flex column justify-center">
        <NoDataFound message="No item found for that id." />
      </div>
    );
  }

  const tabs = [
    {
      label: schema?.label,
      name: schema?.label,
    },
    ...getObjectTabs(relationshipsTabs, objectDetailsData),
    // Includes the task tab only for specific objects,
    schema?.inherit_from?.includes(TASK_TARGET) && {
      label: "Tasks",
      name: TASK_TAB,
      count: taskData?.count ?? 0,
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
    <>
      {!hideHeaders && (
        <Tabs
          tabs={tabs}
          rightItems={
            <>
              {schema.kind === ARTIFACT_DEFINITION_OBJECT && <Generate />}

              <ButtonWithTooltip
                disabled={!permission.write.allow}
                tooltipEnabled
                tooltipContent={permission.write.message ?? "Edit object"}
                onClick={() => setShowEditDrawer(true)}
                className="mr-4 rounded-full text-custom-blue-600 p-4"
                variant={"outline"}
                size={"icon"}
                data-testid="edit-button">
                <Icon icon="mdi:pencil" className="" aria-hidden="true" />
              </ButtonWithTooltip>

              {!schema.kind?.match(/Core.*Group/g)?.length && ( // Hide group buttons on group list view
                <GroupsManagerTriggerButton
                  schema={schema}
                  objectId={objectid}
                  className="text-custom-blue-600 p-4"
                />
              )}
            </>
          }
        />
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
                        header={
                          <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b">
                            <div className="font-semibold">{attribute.label}</div>
                            <ButtonWithTooltip
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
                            </ButtonWithTooltip>
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
            const relationshipSchema = schema?.relationships?.find(
              (relation) => relation?.name === relationship?.name
            );

            const relationshipData = relationship?.paginated
              ? objectDetailsData[relationship.name]?.edges
              : objectDetailsData[relationship.name];

            return (
              <RelationshipDetails
                parentNode={objectDetailsData}
                mode="DESCRIPTION-LIST"
                parentSchema={schema}
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
          parentSchema={schema}
          refetchObjectDetails={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
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
                <span className="font-semibold text-gray-900 truncate">{schema.label}</span>

                <Icon icon="mdi:chevron" className="w-4 h-4 flex-shrink-0 text-gray-400" />

                <span className="flex-grow text-gray-500 overflow-hidden break-words line-clamp-3">
                  {objectDetailsData.display_label}
                </span>
              </div>

              <div className="flex items-center ml-3">
                <Icon icon="mdi:layers-triple" />
                <span className="ml-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</span>
              </div>
            </div>

            <div className="">{schema?.description}</div>

            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
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
          onUpdateComplete={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
          objectid={objectid!}
          objectname={objectname!}
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
          onUpdateComplete={() => graphqlClient.refetchQueries({ include: [schema.kind!] })}
          attributeOrRelationshipToEdit={
            objectDetailsData[metaEditFieldDetails?.attributeOrRelationshipName]?.properties ||
            objectDetailsData[metaEditFieldDetails?.attributeOrRelationshipName]
          }
          schema={schema}
          attributeOrRelationshipName={metaEditFieldDetails?.attributeOrRelationshipName}
          type={metaEditFieldDetails?.type!}
          row={objectDetailsData}
        />
      </SlideOver>
    </>
  );
}
