import { gql } from "@apollo/client";
import { ChevronRightIcon } from "@heroicons/react/20/solid";
import { LockClosedIcon, PencilSquareIcon, RectangleGroupIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { BUTTON_TYPES, Button } from "../../components/buttons/button";
import MetaDetailsTooltip from "../../components/display/meta-details-tooltips";
import SlideOver from "../../components/display/slide-over";
import { File } from "../../components/file";
import { Tabs } from "../../components/tabs";
import { CONFIG } from "../../config/config";
import { ARTIFACT_OBJECT, DEFAULT_BRANCH_NAME, MENU_EXCLUDELIST } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { AuthContext } from "../../decorators/auth";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import {
  getObjectAttributes,
  getObjectRelationships,
  getSchemaObjectColumns,
  getTabs,
} from "../../utils/getSchemaObjectColumns";
import ErrorScreen from "../error-screen/error-screen";
import AddObjectToGroup from "../groups/add-object-to-group";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";
import RelationshipDetails from "../object-item-details/relationship-details-paginated";
import { RelationshipsDetails } from "../object-item-details/relationships-details-paginated";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";
import { Generate } from "./generate";

export default function ArtifactsDetails() {
  const { objectid } = useParams();

  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const [showAddToGroupDrawer, setShowAddToGroupDrawer] = useState(false);
  const auth = useContext(AuthContext);
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);
  const branch = useAtomValue(currentBranchAtom);

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericList] = useAtom(genericsState);
  const schema = schemaList.find((s) => s.kind === ARTIFACT_OBJECT);
  const generic = genericList.find((s) => s.kind === ARTIFACT_OBJECT);
  const navigate = useNavigate();
  useTitle("Artifact details");

  const schemaData = generic || schema;

  if ((schemaList?.length || genericList?.length) && !schemaData) {
    // If there is no schema nor generics, go to home page
    navigate("/");
  }

  if (schemaData && MENU_EXCLUDELIST.includes(schemaData.kind)) {
    navigate("/");
  }
  const attributes = getObjectAttributes(schemaData);
  const relationships = getObjectRelationships(schemaData);
  const columns = getSchemaObjectColumns(schemaData);
  const relationshipsTabs = getTabs(schemaData);

  const queryString = schemaData
    ? getObjectDetailsPaginated({
        kind: schemaData.kind,
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

  const fileUrl = CONFIG.ARTIFACTS_CONTENT_URL(objectDetailsData?.storage_id?.value);

  return (
    <div className="flex-1 overflow-auto flex flex-col">
      <div className="bg-custom-white px-4 py-5 flex items-center">
        <div
          onClick={() => navigate(constructPath(`/objects/${ARTIFACT_OBJECT}`))}
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline">
          {schemaData.name}
        </div>
        <ChevronRightIcon
          className="w-4 h-4 mt-1 mx-2 flex-shrink-0 text-gray-400"
          aria-hidden="true"
        />
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{objectDetailsData.display_label}</p>
      </div>

      <div className="px-4 text-sm">{schemaData?.description}</div>

      <Tabs
        tabs={tabs}
        rightItems={
          <>
            <Generate
              label="Re-generate"
              artifactid={objectid}
              definitionid={objectDetailsData?.definition?.node?.id}
            />

            <Button
              disabled={!auth?.permissions?.write}
              onClick={() => setShowAddToGroupDrawer(true)}
              className="mr-4">
              Manage groups
              <RectangleGroupIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
            </Button>
          </>
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
                    className="cursor-pointer underline">
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
                        )}>
                        {attribute.name === "storage_id" &&
                          objectDetailsData[attribute.name]?.value && (
                            <a
                              href={CONFIG.STORAGE_DETAILS_URL(
                                objectDetailsData[attribute.name].value
                              )}
                              target="_blank"
                              rel="noreferrer"
                              className="cursor-pointer underline">
                              {objectDetailsData[attribute.name].value}
                            </a>
                          )}

                        {attribute.name !== "storage_id" &&
                          getObjectItemDisplayValue(objectDetailsData, attribute, schemaKindName)}
                      </dd>

                      {objectDetailsData[attribute.name] && (
                        <div className="px-2">
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
                                  data-cy="metadata-edit-button">
                                  <PencilSquareIcon className="w-4 h-4 text-custom-blue-500" />
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
                <p className="mt-1 max-w-2xl text-sm text-gray-500">
                  {objectDetailsData.display_label}
                </p>
              </div>

              <div className="flex-1"></div>

              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="text-sm">{schemaData?.description}</div>

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
          objectname={ARTIFACT_OBJECT}
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
                <p className="mt-1 max-w-2xl text-sm text-gray-500">
                  {objectDetailsData.display_label}
                </p>
              </div>

              <div className="flex-1"></div>

              <div className="flex items-center">
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>

            <div className="text-sm">{schemaData?.description}</div>

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
