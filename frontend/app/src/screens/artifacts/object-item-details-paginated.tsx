import { BUTTON_TYPES, Button } from "@/components/buttons/button";
import MetaDetailsTooltip from "@/components/display/meta-details-tooltips";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { File } from "@/components/file";
import { Tabs } from "@/components/tabs";
import { CONFIG } from "@/config/config";
import { ARTIFACT_OBJECT, MENU_EXCLUDELIST } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import { useAuth } from "@/hooks/useAuth";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import { Generate } from "@/screens/artifacts/generate";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import { GroupsManagerTriggerButton } from "@/screens/groups/groups-manager-trigger-button";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import RelationshipDetails from "@/screens/object-item-details/relationship-details-paginated";
import { RelationshipsDetails } from "@/screens/object-item-details/relationships-details-paginated";
import ObjectItemMetaEdit from "@/screens/object-item-meta-edit/object-item-meta-edit";
import { getPermission } from "@/screens/permission/utils";
import { showMetaEditState } from "@/state/atoms/metaEditFieldDetails.atom";
import { genericsState, schemaState } from "@/state/atoms/schema.atom";
import { schemaKindNameState } from "@/state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "@/state/atoms/showMetaEdit.atom copy";
import { classNames } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { getObjectItemDisplayValue } from "@/utils/getObjectItemDisplayValue";
import {
  getObjectAttributes,
  getObjectRelationships,
  getSchemaObjectColumns,
  getTabs,
} from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { LockClosedIcon, RectangleGroupIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Link, Navigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import UnauthorizedScreen from "../errors/unauthorized-screen";

export default function ArtifactsDetails() {
  const { objectid } = useParams();

  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const auth = useAuth();
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericList] = useAtom(genericsState);
  const schema = schemaList.find((s) => s.kind === ARTIFACT_OBJECT);
  const generic = genericList.find((s) => s.kind === ARTIFACT_OBJECT);
  useTitle("Artifact details");

  const schemaData = generic || schema;

  if ((schemaList?.length || genericList?.length) && !schemaData) {
    // If there is no schema nor generics, go to home page
    return <Navigate to="/" />;
  }

  if (schemaData && MENU_EXCLUDELIST.includes(schemaData.kind)) {
    return <Navigate to="/" />;
  }

  const attributes = getObjectAttributes({ schema: schemaData });
  const relationships = getObjectRelationships({ schema: schemaData });
  const columns = getSchemaObjectColumns({ schema: schemaData });
  const relationshipsTabs = getTabs(schemaData);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        kind: schemaData.kind,
        columns,
        relationshipsTabs,
        objectid,
        hasPermissions: true,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, error, data, refetch } = useQuery(query, { skip: !schemaData });

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching object details." />;
  }

  if (loading || !schemaData) {
    return <LoadingScreen />;
  }

  if (!data || (data && !data[schemaData.kind]?.edges?.length)) {
    // Redirect to the main list if there is no item for this is
    // navigate(`/objects/${objectname}`);

    return <NoDataFound message="No item found for that id." />;
  }

  const objectDetailsData = data[schemaData.kind]?.edges[0]?.node;

  const permission = getPermission(
    schemaData.kind && data && data[schemaData?.kind]?.permissions?.edges
  );

  const tabs = [
    {
      label: schemaData?.label,
      name: schemaData?.label,
    },
    ...getTabs(schemaData, objectDetailsData),
  ];

  if (!objectDetailsData) {
    return null;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  const fileUrl = CONFIG.ARTIFACTS_CONTENT_URL(objectDetailsData?.storage_id?.value);

  return (
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-1">
            <Link to={constructPath(`/objects/${ARTIFACT_OBJECT}`)} className="hover:underline">
              {schemaData.name}
            </Link>
            <Icon icon="mdi:chevron-right" className="text-2xl shrink-0 text-gray-400" />
            <p className="max-w-2xl text-sm text-gray-500 font-normal">
              {objectDetailsData.display_label}
            </p>
          </div>
        }
      />

      <div className="px-4 text-sm">{schemaData?.description}</div>

      <Tabs
        tabs={tabs}
        rightItems={
          <div className="pr-2">
            <Generate
              label="Re-generate"
              artifactid={objectid}
              definitionid={objectDetailsData?.definition?.node?.id}
            />

            <GroupsManagerTriggerButton
              schema={schemaData}
              objectId={objectid}
              permission={permission}
              size="default"
              variant="outline"
            >
              Manage groups
              <RectangleGroupIcon className="ml-2 h-4 w-4" aria-hidden="true" />
            </GroupsManagerTriggerButton>
          </div>
        }
      />

      {!qspTab && (
        <div className="flex flex-col-reverse xl:flex-row">
          <div className="flex-2">
            <File url={fileUrl} enableCopy />
          </div>

          <div className="flex-1 bg-custom-white p-4 min-w-[500px]">
            <dl className="sm:divide-y sm:divide-gray-200">
              <div className="p-2 grid grid-cols-3 gap-4 text-xs">
                <dt className="text-sm font-medium text-gray-500 flex items-center">ID</dt>
                <dd className="text-sm text-gray-900 ">
                  <a
                    href={CONFIG.ARTIFACT_DETAILS_URL(objectDetailsData.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="cursor-pointer underline"
                  >
                    {objectDetailsData.id}
                  </a>
                </dd>
              </div>

              {attributes?.map((attribute) => {
                if (
                  !objectDetailsData[attribute.name] ||
                  !objectDetailsData[attribute.name].is_visible
                ) {
                  return null;
                }

                return (
                  <div className="p-2 grid grid-cols-3 gap-4 text-xs" key={attribute.name}>
                    <dt className="text-sm font-medium text-gray-500 flex items-center">
                      {attribute.label}
                    </dt>

                    <div className="flex items-center">
                      <dd
                        className={classNames(
                          "text-sm text-gray-900 "
                          // attribute.kind === "TextArea" ? "whitespace-pre-wrap mr-2" : ""
                        )}
                      >
                        {attribute.name === "storage_id" &&
                          objectDetailsData[attribute.name]?.value && (
                            <a
                              href={CONFIG.STORAGE_DETAILS_URL(
                                objectDetailsData[attribute.name].value
                              )}
                              target="_blank"
                              rel="noreferrer"
                              className="cursor-pointer underline"
                            >
                              {objectDetailsData[attribute.name].value}
                            </a>
                          )}

                        {attribute.name !== "storage_id" &&
                          getObjectItemDisplayValue(objectDetailsData, attribute, schemaKindName)}
                      </dd>

                      {objectDetailsData[attribute.name] && (
                        <div className="px-2">
                          <MetaDetailsTooltip
                            updatedAt={objectDetailsData[attribute.name].updated_at}
                            source={objectDetailsData[attribute.name].source}
                            owner={objectDetailsData[attribute.name].owner}
                            isFromProfile={objectDetailsData[attribute.name].is_from_profile}
                            isProtected={objectDetailsData[attribute.name].is_protected}
                            header={
                              <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b">
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
                                  data-cy="metadata-edit-button"
                                >
                                  <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                                </Button>
                              </div>
                            }
                          />
                        </div>
                      )}

                      {objectDetailsData[attribute.name].is_protected && (
                        <LockClosedIcon className="w-4 h-4" />
                      )}
                    </div>
                  </div>
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
        </div>
      )}

      {qspTab && <RelationshipsDetails parentNode={objectDetailsData} />}

      <SlideOver
        title={
          <SlideOverTitle
            schema={schemaData}
            currentObjectLabel={objectDetailsData?.display_label}
            title={`${metaEditFieldDetails?.label} properties`}
            subtitle={`Update the properties of ${metaEditFieldDetails?.label}`}
          />
        }
        open={showMetaEditModal}
        setOpen={setShowMetaEditModal}
      >
        <ObjectItemMetaEdit
          closeDrawer={() => setShowMetaEditModal(false)}
          onUpdateComplete={() => refetch()}
          attributeOrRelationshipToEdit={
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
