import {
  DEFAULT_BRANCH_NAME,
  GENERIC_REPOSITORY_KIND,
  MENU_EXCLUDELIST,
  TASK_TARGET,
} from "@/config/constants";
import { QSP } from "@/config/qsp";
import { currentBranchAtom } from "@/entities/branches/stores";
import { NodeEvents } from "@/entities/events/ui/node-details-events";
import { ObjectAttributeValue } from "@/entities/nodes/getObjectItemDisplayValue";
import { ActionButtons } from "@/entities/nodes/object-item-details/action-buttons";
import { ObjectAttributeRow } from "@/entities/nodes/object-item-details/object-attribute-row";
import RelationshipDetails from "@/entities/nodes/object-item-details/relationship-details-paginated";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import {
  getObjectAttributes,
  getObjectRelationships,
} from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { ObjectDetailsTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import { ObjectDetailsTabContent } from "@/entities/nodes/relationships/ui/object-details-tab-content";
import { showMetaEditState } from "@/entities/nodes/stores/metaEditFieldDetails.atom";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Permission } from "@/entities/permission/types";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import { ObjectTaskTab } from "@/entities/tasks/ui/task-tab";
import { queryClient } from "@/shared/api/rest/client";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import SlideOver from "@/shared/components/display/slide-over";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { useTitle } from "@/shared/hooks/useTitle";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai";
import { Navigate, useParams } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

type ObjectDetailsProps = {
  schema: ModelSchema;
  objectDetailsData: NodeObject;
  hideHeaders?: boolean;
  permission: Permission;
};

export default function ObjectItemDetails({
  schema,
  objectDetailsData,
  permission,
  hideHeaders,
}: ObjectDetailsProps) {
  const { objectKind, objectid } = useParams();

  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);
  const branch = useAtomValue(currentBranchAtom);
  const [schemaList] = useAtom(nodeSchemasAtom);
  const [genericList] = useAtom(genericSchemasAtom);
  const isTaskTarget = isOfKind(TASK_TARGET, schema);
  const isRepository = isOfKind(GENERIC_REPOSITORY_KIND, schema);

  if ((schemaList?.length || genericList?.length) && !schema) {
    // If there is no schema nor generics, go to home page
    return <Navigate to="/" />;
  }

  if (schema && MENU_EXCLUDELIST.includes(schema.kind!)) {
    return <Navigate to="/" />;
  }

  const attributes = getObjectAttributes({ schema: schema });
  const relationships = getObjectRelationships({ schema: schema });
  const relationshipsTabs = getRelationshipsVisibleInTab(schema.relationships ?? []);

  useTitle(
    objectDetailsData?.display_label
      ? `${objectDetailsData?.display_label} details`
      : `${schema.label} details`
  );

  if (!objectDetailsData) {
    return null;
  }

  return (
    <>
      {!hideHeaders && (
        <header className="flex items-center border-b border-gray-200 px-2">
          <div className="grow flex gap-8 px-4">
            <ObjectDetailsTab
              isActive={!qspTab}
              to={getObjectDetailsUrl(objectKind as string, objectid)}
            >
              {schema.label}
            </ObjectDetailsTab>

            {relationshipsTabs.map((tab) => {
              return (
                <RelationshipTab
                  key={tab.name}
                  objectKind={objectKind as string}
                  objectId={objectDetailsData.id}
                  relationshipSchema={tab as RelationshipSchema}
                />
              );
            })}

            {isTaskTarget && <ObjectTaskTab objectId={objectDetailsData.id} />}
            {isRepository && <RepositoryObjectsTab objectId={objectDetailsData.id} />}
          </div>
          <ActionButtons
            schema={schema}
            objectDetailsData={objectDetailsData}
            permission={permission}
          />
        </header>
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

          <Card className="p-0 overflow-x-hidden" data-testid="activities-panel">
            <CardWithBorder.Title className="border-b border-gray-200">
              Activities
            </CardWithBorder.Title>
            <NodeEvents objectId={objectid} objectKind={objectKind} />
          </Card>
        </div>
      )}

      {qspTab && (
        <ObjectDetailsTabContent objectSchema={schema} objectDetailsData={objectDetailsData} />
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
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes("objects"),
            });
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
