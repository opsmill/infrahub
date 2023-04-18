import { ChevronRightIcon } from "@heroicons/react/20/solid";
import {
  CheckIcon,
  LockClosedIcon,
  PencilIcon,
  PencilSquareIcon,
  XMarkIcon
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";

import { Button } from "../../components/button";
import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import SlideOver from "../../components/slide-over";
import { Tabs } from "../../components/tabs";
import { QSP } from "../../config/constants";
import getObjectDetails from "../../graphql/queries/objects/objectDetails";
import { branchState } from "../../state/atoms/branch.atom";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { timeState } from "../../state/atoms/time.atom";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit.component";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";
import RelationshipDetails from "./relationship-details";
import RelationshipsDetails from "./relationships-details";

export default function ObjectItemDetails() {
  const { objectname, objectid } = useParams();
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);

  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const [showMetaEditModal, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [metaEditFieldDetails, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const [objectDetails, setObjectDetails] = useState<any | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const atttributeRelationships = schema?.relationships?.filter((relationship) => {
    if(relationship.kind === "Generic" && relationship.cardinality === "one") {
      return true;
    }
    if(relationship.kind === "Attribute") {
      return true;
    }
    if(relationship.kind === "Component" && relationship.cardinality === "one") {
      return true;
    }
    if(relationship.kind === "Parent") {
      return true;
    }
    return false;
  }) ?? [];

  const tabs = [
    {
      label: schema?.label,
      name: schema?.label
    },
    ...(schema?.relationships || []).filter(relationship => {
      if(relationship.kind === "Generic" && relationship.cardinality === "many") {
        return true;
      }
      if(relationship.kind === "Component" && relationship.cardinality === "many") {
        return true;
      }
      return false;
    })
    .map((relationship) => ({ label: relationship.label, name: relationship.name}))
  ];

  const navigate = useNavigate();

  const fetchObjectDetails = useCallback(async () => {
    setHasError(false);
    setIsLoading(true);
    setObjectDetails(undefined);
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

  return (
    <div className="bg-white flex-1 overflow-auto flex flex-col">
      <div className="px-4 py-5 sm:px-6 flex items-center">
        <div
          onClick={() => navigate(`/objects/${objectname}`)}
          className="text-base font-semibold leading-6 text-gray-900 cursor-pointer hover:underline"
        >
          {schema.kind}
        </div>
        <ChevronRightIcon
          className="h-5 w-5 mt-1 mx-2 flex-shrink-0 text-gray-400"
          aria-hidden="true"
        />
        <p className="mt-1 max-w-2xl text-sm text-gray-500">{objectDetails.display_label}</p>
      </div>

      <Tabs
        tabs={tabs}
        rightItems={
          (
            <Button onClick={() => {
              setShowEditDrawer(true);
            }} className="mr-4">
              Edit
              <PencilIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
            </Button>
          )
        }
      />

      {
        !qspTab
        && (
          <div className="px-4 py-5 sm:p-0">
            <dl className="sm:divide-y sm:divide-gray-200">
              <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6">
                <dt className="text-sm font-medium text-gray-500 flex items-center">ID</dt>
                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                  {objectDetails.id}
                </dd>
              </div>
              {
                schema
                .attributes
                ?.map(
                  (attribute) => {
                    if (!objectDetails[attribute.name] || !objectDetails[attribute.name].is_visible) {
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
                            {typeof objectDetails[attribute.name]?.value !== "boolean" ? objectDetails[attribute.name].value ? objectDetails[attribute.name].value : "-" : ""}
                            { typeof objectDetails[attribute.name]?.value === "boolean" &&
                              <span className="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-1.5 text-sm font-medium text-gray-800">
                                {objectDetails[attribute.name]?.value === true && (<CheckIcon className="h-4 w-4" />)}
                                {objectDetails[attribute.name]?.value === false && (<XMarkIcon className="h-4 w-4" />)}
                              </span>
                            }
                          </dd>

                          {
                            objectDetails[attribute.name]
                            && (
                              <MetaDetailsTooltip items={[
                                {
                                  label: "Updated at",
                                  value: objectDetails[attribute.name].updated_at,
                                  type: "date",
                                },
                                {
                                  label: "Update time",
                                  value: `${new Date(objectDetails[attribute.name].updated_at).toLocaleDateString()} ${new Date(objectDetails[attribute.name].updated_at).toLocaleTimeString()}`,
                                  type: "text",
                                },
                                {
                                  label: "Source",
                                  value: objectDetails[attribute.name].source,
                                  type: "link"
                                },
                                {
                                  label: "Owner",
                                  value: objectDetails[attribute.name].owner,
                                  type: "link"
                                },
                                {
                                  label: "Is protected",
                                  value: objectDetails[attribute.name].is_protected ? "True" : "False",
                                  type: "text"
                                },
                                {
                                  label: "Is inherited",
                                  value: objectDetails[attribute.name].is_inherited ? "True" : "False",
                                  type: "text"
                                },
                              ]}
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
                              />
                            )
                          }

                          {
                            objectDetails[attribute.name].is_protected
                            && (
                              <LockClosedIcon className="h-5 w-5 ml-2" />
                            )
                          }
                        </div>
                      </div>
                    );
                  }
                )}

              {
                atttributeRelationships
                ?.map(
                  (relationshipSchema: any) => <RelationshipDetails parentSchema={schema} refreshObject={fetchObjectDetails} key={relationshipSchema.name} relationshipsData={objectDetails[relationshipSchema.name]} relationshipSchema={relationshipSchema} />
                )
              }
            </dl>
          </div>
        )
      }

      {
        qspTab
        && (
          <RelationshipsDetails parentSchema={schema} refreshObject={fetchObjectDetails} />
        )
      }

      <SlideOver title={`Edit ${schema.label}`} subtitle={objectDetails.display_label} open={showEditDrawer} setOpen={setShowEditDrawer}>
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