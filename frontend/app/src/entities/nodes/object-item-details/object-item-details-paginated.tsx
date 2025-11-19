import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai";
import { useQueryState } from "nuqs";
import { useCallback } from "react";
import { Navigate, useParams } from "react-router";

import {
  DEFAULT_BRANCH_NAME,
  GENERIC_REPOSITORY_KIND,
  MENU_EXCLUDELIST,
  TASK_TARGET,
} from "@/config/constants";
import { QSP } from "@/config/qsp";

import { queryClient } from "@/shared/api/rest/client";
import SlideOver from "@/shared/components/display/slide-over";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import { useTitle } from "@/shared/hooks/useTitle";

import { currentBranchAtom } from "@/entities/branches/stores";
import { NodeEvents } from "@/entities/events/ui/node-details-events";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { ObjectDetailsContent } from "@/entities/nodes/object/ui/object-details-content";
import { ObjectDetailsTab, RelationshipTab } from "@/entities/nodes/object/ui/object-tabs";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInTab } from "@/entities/nodes/object/utils/get-relationships-visible-in-tab";
import { ActionButtons } from "@/entities/nodes/object-item-details/action-buttons";
import ObjectItemMetaEdit from "@/entities/nodes/object-item-meta-edit/object-item-meta-edit";
import { ObjectDetailsTabContent } from "@/entities/nodes/relationships/ui/object-details-tab-content";
import { showMetaEditState } from "@/entities/nodes/stores/metaEditFieldDetails.atom";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import { RepositoryObjectsTab } from "@/entities/repository/ui/repository-objects-tab";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { AttributeSchema, ModelSchema, RelationshipSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import { ObjectTaskTab } from "@/entities/tasks/ui/task-tab";

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
  const { objectKind, objectId } = useParams();

  const [qspTab] = useQueryState(QSP.TAB);
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);
  const branch = useAtomValue(currentBranchAtom);
  const [schemaList] = useAtom(nodeSchemasAtom);
  const [genericList] = useAtom(genericSchemasAtom);
  const isTaskTarget = isOfKind(TASK_TARGET, schema);
  const isRepository = isOfKind(GENERIC_REPOSITORY_KIND, schema);

  const handleMetadataClick = useCallback(
    (attribute: AttributeSchema) => {
      setMetaEditFieldDetails({
        type: "attribute",
        attributeOrRelationshipName: attribute.name,
        label: attribute.label || attribute.name,
      });

      setShowMetaEditModal(true);
    },
    [setMetaEditFieldDetails, setShowMetaEditModal]
  );

  if ((schemaList?.length || genericList?.length) && !schema) {
    // If there is no schema nor generics, go to home page
    return <Navigate to="/" />;
  }

  if (schema && MENU_EXCLUDELIST.includes(schema.kind!)) {
    return <Navigate to="/" />;
  }

  const relationshipsTabs = getRelationshipsVisibleInTab(schema.relationships ?? []);

  useTitle(
    objectDetailsData
      ? `${getNodeLabel(objectDetailsData)} details`
      : `${schema.label} details`
  );

  if (!objectDetailsData) {
    return null;
  }

  return (
    <>
      {!hideHeaders && (
        <header className="flex items-center border-gray-200 border-b px-2">
          <ScrollArea scrollX scrollBarClassName="hidden" className="grow">
            <div className="flex grow gap-8 px-4" data-testid="object-details-tabs">
              <ObjectDetailsTab
                isActive={!qspTab}
                to={getObjectDetailsUrl(objectKind as string, objectId)}
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
          </ScrollArea>
          <ActionButtons
            schema={schema}
            objectDetailsData={objectDetailsData}
            permission={permission}
          />
        </header>
      )}

      {!qspTab && (
        <div className="flex flex-col gap-2 overflow-auto p-2 xl:grid xl:grid-cols-3 xl:items-start">
          <Card className="grow overflow-x-hidden p-0 md:col-span-2" data-testid="object-details">
            <CardWithBorder.Title className="border-gray-200 border-b">
              Details
            </CardWithBorder.Title>

            <ObjectDetailsContent
              schema={schema}
              objectDetailsData={objectDetailsData}
              permission={permission}
              onClickMetadata={handleMetadataClick}
            />
          </Card>

          <Card className="overflow-x-hidden p-0" data-testid="activities-panel">
            <CardWithBorder.Title className="border-gray-200 border-b">
              Activities
            </CardWithBorder.Title>
            <NodeEvents objectId={objectId} objectKind={objectKind} />
          </Card>
        </div>
      )}

      {qspTab && (
        <ObjectDetailsTabContent objectSchema={schema} objectDetailsData={objectDetailsData} />
      )}

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex w-full items-center">
              <span className="mr-3 font-semibold text-lg">{metaEditFieldDetails?.label}</span>
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
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
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
