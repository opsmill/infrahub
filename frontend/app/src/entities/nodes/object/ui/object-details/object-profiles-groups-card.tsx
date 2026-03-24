import { Icon } from "@iconify-icon/react";
import { ChevronDownIcon, ChevronUpIcon, PenLineIcon } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { GroupsManager } from "@/entities/groups/ui/groups-manager";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { useGetProfiles } from "@/entities/nodes/profiles/domain/get-profiles.query";
import type {
  NodeCore,
  NodeObjectWithMetadata,
  NodeRelationshipManyWithMetadata,
  NodeRelationshipMetadata,
  NodeRelationshipOneWithMetadata,
} from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import { getSchema } from "@/entities/schema/domain/get-schema";
import type { ModelSchema, NodeSchema } from "@/entities/schema/types";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

const VISIBLE_ITEMS_LIMIT = 5;

interface GroupNode extends NodeCore {
  group_type?: { value: string | null } | null;
}

interface RelationshipEdge<T extends NodeCore = NodeCore> {
  node: T;
  properties: NodeRelationshipMetadata;
}

function getRelationshipManyEdges<T extends NodeCore>(
  objectData: NodeObjectWithMetadata,
  relationshipName: string
): RelationshipEdge<T>[] {
  const relationship = objectData[relationshipName] as NodeRelationshipManyWithMetadata | undefined;
  if (!relationship) return [];

  return relationship.edges.filter(
    (edge): edge is NodeRelationshipOneWithMetadata & { node: T } => edge.node !== null
  );
}

function Section({ children }: { children: ReactNode }) {
  return <div className="p-3">{children}</div>;
}

function SectionHeader({ children }: { children: ReactNode }) {
  return <div className="mb-2 flex items-center gap-2">{children}</div>;
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="font-semibold text-gray-700 text-sm">{children}</h3>;
}

function SectionEmptyMessage({ children }: { children: ReactNode }) {
  return <p className="text-gray-500 text-sm">{children}</p>;
}

function ShowMoreButton({ showAll, onClick }: { showAll: boolean; onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="h-auto gap-1 px-0.5 text-gray-500 text-xs"
    >
      {showAll ? (
        <>
          Less <ChevronUpIcon className="size-3" />
        </>
      ) : (
        <>
          More <ChevronDownIcon className="size-3" />
        </>
      )}
    </Button>
  );
}

interface ProfilesListProps {
  objectData: NodeObjectWithMetadata;
  objectSchema: NodeSchema;
  permission: Permission;
}

function ProfilesList({ objectData, objectSchema, permission }: ProfilesListProps) {
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const profileEdges = getRelationshipManyEdges(objectData, "profiles");
  const nodeLabel = getNodeLabel(objectData);
  const isEditAllowed = permission.update.isAllowed;

  const hasMoreItems = profileEdges.length > VISIBLE_ITEMS_LIMIT;
  const displayedEdges = showAll ? profileEdges : profileEdges.slice(0, VISIBLE_ITEMS_LIMIT);

  const content =
    profileEdges.length === 0 ? (
      <SectionEmptyMessage>-</SectionEmptyMessage>
    ) : (
      <Col className="items-start">
        <div className="flex flex-wrap gap-1">
          {displayedEdges.map((edge) => (
            <div key={edge.node.id} className="flex items-center">
              <Link
                className={classNames(
                  "rounded-md border border-transparent p-0",
                  focusVisibleStyle
                )}
                to={getObjectDetailsUrl(edge.node.__typename, edge.node.id)}
                onClick={(e) => e.stopPropagation()}
              >
                <Badge variant="green" className="gap-1 font-normal hover:underline">
                  <Icon icon="mdi:shape-plus-outline" />
                  {getNodeLabel(edge.node)}
                </Badge>
              </Link>
              <MetaDetailsTooltip
                updatedAt={edge.properties.updated_at}
                source={edge.properties.source}
                owner={edge.properties.owner}
                isProtected={edge.properties.is_protected}
              />
            </div>
          ))}
        </div>
        {hasMoreItems && <ShowMoreButton showAll={showAll} onClick={() => setShowAll(!showAll)} />}
      </Col>
    );

  return (
    <>
      {isEditAllowed ? (
        <Row
          className="group cursor-pointer rounded-lg p-2 hover:bg-neutral-100"
          onClick={() => setIsEditModalOpen(true)}
        >
          {content}
          <PenLineIcon className="ml-auto size-3.5 shrink-0 text-neutral-400 opacity-0 group-hover:opacity-100" />
        </Row>
      ) : (
        content
      )}

      <SlideOver
        title={
          <SlideOverTitle
            schema={objectSchema}
            currentObjectLabel={nodeLabel}
            title={`Edit ${nodeLabel}`}
            subtitle={objectSchema.description}
          />
        }
        open={isEditModalOpen}
        setOpen={setIsEditModalOpen}
      >
        <ObjectItemEditComponent
          closeDrawer={() => setIsEditModalOpen(false)}
          onUpdateComplete={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsEditModalOpen(false);
          }}
          objectId={objectData.id}
          objectname={objectSchema.kind!}
        />
      </SlideOver>
    </>
  );
}

interface GroupsListProps {
  objectData: NodeObjectWithMetadata;
  objectSchema: ModelSchema;
  permission: Permission;
}

function GroupsList({ objectData, objectSchema, permission }: GroupsListProps) {
  const [isManageGroupsDrawerOpen, setIsManageGroupsDrawerOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const allGroups = getRelationshipManyEdges<GroupNode>(objectData, "member_of_groups");
  const groups = allGroups.filter(({ node }) => node.group_type?.value !== "internal");
  const nodeLabel = getNodeLabel(objectData);
  const isEditAllowed = permission.update.isAllowed;

  const hasMoreItems = groups.length > VISIBLE_ITEMS_LIMIT;
  const displayedEdges = showAll ? groups : groups.slice(0, VISIBLE_ITEMS_LIMIT);

  const content =
    groups.length === 0 ? (
      <SectionEmptyMessage>-</SectionEmptyMessage>
    ) : (
      <Col className="items-start">
        <div className="flex flex-wrap gap-1">
          {displayedEdges.map((edge) => {
            const { schema } = getSchema(edge.node.__typename);
            const icon = getSchemaIcon(schema);

            return (
              <div key={edge.node.id} className="flex items-center">
                <Link
                  className={classNames(
                    "rounded-md border border-transparent p-0",
                    focusVisibleStyle
                  )}
                  to={getObjectDetailsUrl(edge.node.__typename, edge.node.id)}
                  onClick={(e) => e.stopPropagation()}
                >
                  <Badge variant="blue" className="gap-1 font-normal hover:underline">
                    <Icon icon={icon} />
                    {getNodeLabel(edge.node)}
                  </Badge>
                </Link>
                <MetaDetailsTooltip
                  updatedAt={edge.properties.updated_at}
                  source={edge.properties.source}
                  owner={edge.properties.owner}
                  isProtected={edge.properties.is_protected}
                />
              </div>
            );
          })}
        </div>
        {hasMoreItems && <ShowMoreButton showAll={showAll} onClick={() => setShowAll(!showAll)} />}
      </Col>
    );

  return (
    <>
      {isEditAllowed ? (
        <Row
          className="group cursor-pointer rounded-lg p-2 hover:bg-neutral-100"
          onClick={() => setIsManageGroupsDrawerOpen(true)}
        >
          {content}
          <PenLineIcon className="ml-auto size-3.5 shrink-0 text-neutral-400 opacity-0 group-hover:opacity-100" />
        </Row>
      ) : (
        content
      )}

      <SlideOver
        title={
          <SlideOverTitle
            schema={objectSchema}
            currentObjectLabel={nodeLabel}
            title="Manage groups"
            subtitle="Add and unassign groups"
          />
        }
        open={isManageGroupsDrawerOpen}
        setOpen={setIsManageGroupsDrawerOpen}
      >
        <GroupsManager
          schema={objectSchema}
          objectId={objectData.id}
          onUpdateCompleted={() => queryClient.invalidateQueries({ queryKey: objectQueryKeys.all })}
          className="overflow-auto p-4"
        />
      </SlideOver>
    </>
  );
}

interface ObjectProfilesGroupsCardProps {
  objectSchema: ModelSchema;
  objectData: NodeObjectWithMetadata;
  permission: Permission;
  className?: string;
}

export function ObjectProfilesGroupsCard({
  objectSchema,
  objectData,
  permission,
  className,
}: ObjectProfilesGroupsCardProps) {
  const schemaSupportsProfiles =
    "generate_profile" in objectSchema && objectSchema.generate_profile;
  const showGroups = !isOfKind("CoreGroup", objectSchema);

  // Check if object already has assigned profiles
  const objectProfileEdges = getRelationshipManyEdges(objectData, "profiles");
  const hasAssignedProfiles = objectProfileEdges.length > 0;

  // Only fetch available profile types if object has no assigned profiles
  const { data: availableProfiles } = useGetProfiles(
    { schema: objectSchema as NodeSchema },
    { enabled: schemaSupportsProfiles && !hasAssignedProfiles }
  );

  // Show profiles section if:
  // - Object has assigned profiles, OR
  // - Object has no assigned profiles but profile types exist for this schema
  const showProfilesSection =
    hasAssignedProfiles || (availableProfiles && availableProfiles.length > 0);

  if (!showProfilesSection && !showGroups) {
    return null;
  }

  const getCardTitle = () => {
    if (showProfilesSection && showGroups) return "Profiles & Groups";
    if (showProfilesSection) return "Profiles";
    return "Groups";
  };

  return (
    <Card className={classNames("divide-y divide-gray-200 overflow-x-hidden p-0", className)}>
      <CardWithBorder.Title>{getCardTitle()}</CardWithBorder.Title>

      {showProfilesSection && (
        <Section>
          <SectionHeader>
            <SectionTitle>Profiles</SectionTitle>
          </SectionHeader>
          <ProfilesList
            objectData={objectData}
            objectSchema={objectSchema as NodeSchema}
            permission={permission}
          />
        </Section>
      )}

      {showGroups && (
        <Section>
          {showProfilesSection && (
            <SectionHeader>
              <SectionTitle>Groups</SectionTitle>
            </SectionHeader>
          )}
          <GroupsList objectData={objectData} objectSchema={objectSchema} permission={permission} />
        </Section>
      )}
    </Card>
  );
}
