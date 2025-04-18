import { DEFAULT_BRANCH_NAME, MENU_EXCLUDELIST, TASK_TAB, TASK_TARGET } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { currentBranchAtom } from "@/entities/branches/stores";
import {
  AttributeType,
  Node,
  ObjectAttributeValue,
  RelationshipType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import {
  getObjectAttributes,
  getObjectRelationships,
  getObjectTabs,
  getTabs,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { ObjectRelationshipsManager } from "@/entities/nodes/relationships/ui/object-relationships-manager";
import { showMetaEditState } from "@/entities/nodes/stores/metaEditFieldDetails.atom";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import { Permission } from "@/entities/permission/types";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { ModelSchema } from "@/entities/schema/types";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";
import { TaskItems } from "@/entities/tasks/ui/task-items";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import SlideOver from "@/shared/components/display/slide-over";
import { Tabs } from "@/shared/components/tabs";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Link } from "@/shared/components/ui/link";
import { useTitle } from "@/shared/hooks/useTitle";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useRef } from "react";
import { Navigate, useLocation, useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";
import { NodeEvents } from "../../events/ui/node-details-events";
import { ActionButtons } from "./action-buttons";
import { ObjectAttributeRow } from "./object-attribute-row";
import RelationshipDetails from "./relationship-details-paginated";

type ObjectDetailsProps = {
  schema: ModelSchema;
  objectDetailsData: Node & Record<string, AttributeType | RelationshipType>;
  taskData?: Object;
  hideHeaders?: boolean;
  permission: Permission;
};

export default function ObjectItemDetails({
  schema,
  objectDetailsData,
  permission,
  taskData,
  hideHeaders,
}: ObjectDetailsProps) {
  const location = useLocation();
  const { objectKind, objectid } = useParams();
  const { pathname } = location;

  const [qspTab, setQspTab] = useQueryParam(QSP.TAB, StringParam);
  const [qspTaskId, setQspTaskId] = useQueryParam(QSP.TASK_ID, StringParam);
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);
  const branch = useAtomValue(currentBranchAtom);
  const [schemaList] = useAtom(nodeSchemasAtom);
  const [genericList] = useAtom(genericSchemasAtom);

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
      : `${schema.label} details`
  );

  const tabs = [
    {
      label: schema?.label,
      name: schema?.name,
    },
    ...getObjectTabs(relationshipsTabs, objectDetailsData),
    // Includes the task tab only for specific nodes,
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
            <ActionButtons
              schema={schema}
              objectDetailsData={objectDetailsData}
              permission={permission}
            />
          }
        />
      )}

      {!qspTab && (
        <div className="flex flex-col xl:items-start xl:grid xl:grid-cols-3 gap-2 p-2">
          <Card className="md:col-span-2 p-0 grow overflow-x-hidden">
            <CardWithBorder.Title className="border-b border-gray-200">
              Details
            </CardWithBorder.Title>

            <div className="divide-y divide-gray-200">
              {attributes.map((attribute) => {
                if (!objectDetailsData[attribute.name]) {
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
                            updatedAt={objectDetailsData[attribute.name]?.updated_at}
                            source={objectDetailsData[attribute.name]?.source}
                            owner={objectDetailsData[attribute.name]?.owner}
                            isFromProfile={objectDetailsData[attribute.name]?.is_from_profile}
                            isProtected={objectDetailsData[attribute.name]?.is_protected}
                            header={
                              !attribute.read_only && (
                                <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b border-gray-200">
                                  <div className="font-semibold">{attribute.label}</div>
                                  <ButtonWithTooltip
                                    disabled={!permission.update.isAllowed}
                                    tooltipEnabled={!permission.update.isAllowed}
                                    tooltipContent={permission.update.message}
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
                                    data-cy="metadata-edit-button"
                                  >
                                    <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                                  </ButtonWithTooltip>
                                </div>
                              )
                            }
                          />
                        )}

                        {objectDetailsData[attribute.name]?.is_protected && (
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
            </div>
          </Card>

          <Card className="p-0 overflow-x-hidden">
            <CardWithBorder.Title className="border-b border-gray-200">
              Activities
            </CardWithBorder.Title>
            <NodeEvents objectId={objectid} objectKind={objectKind} />
          </Card>
        </div>
      )}

      {qspTab && qspTab !== TASK_TAB && (
        <ObjectRelationshipsManager
          parentNodeSchema={schema}
          parentNodeId={objectDetailsData.id}
          relationshipName={qspTab}
        />
      )}

      {qspTab && qspTab === TASK_TAB && !qspTaskId && (
        <TaskItems ref={refetchRef} hideRelatedNode />
      )}

      {qspTab && qspTab === TASK_TAB && qspTaskId && (
        <div>
          <div className="flex bg-white text-sm">
            <Link
              to={constructPath(pathname, [
                { name: QSP.TAB, value: TASK_TAB },
                { name: QSP.TASK_ID, exclude: true },
              ])}
              className="flex items-center p-2 "
            >
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
        setOpen={setShowMetaEditModal}
      >
        <ObjectItemMetaEdit
          closeDrawer={() => setShowMetaEditModal(false)}
          onUpdateComplete={() => {
            graphqlClient.refetchQueries({ include: [schema.kind!, "GET_EVENTS"] });
            queryClient.invalidateQueries({ queryKey: ["events", [objectid]] });
          }}
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
