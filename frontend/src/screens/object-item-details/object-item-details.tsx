import { ChevronRightIcon } from "@heroicons/react/20/solid";
import {
  CheckIcon,
  LockClosedIcon,
  PencilIcon,
  XMarkIcon
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";

import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import { branchState } from "../../state/atoms/branch.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { timeState } from "../../state/atoms/time.atom";
import getObjectDetails from "../../graphql/queries/objects/objectDetails";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";
import RelationshipDetails from "./relationship-details";
import { QSP } from "../../config/constants";
import { Button } from "../../components/button";
import RelationshipsDetails from "./relationships-details";
import { Tabs } from "../../components/tabs";

export default function ObjectItemDetails() {
  const { objectname, objectid } = useParams();
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [date] = useAtom(timeState);
  const [branch] = useAtom(branchState);

  const [objectDetails, setObjectDetails] = useState<any | undefined>();
  const [schemaList] = useAtom(schemaState);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const atttributeRelationships = schema?.relationships?.filter((relationship) => relationship.kind === "Attribute") ?? [];
  const otherRelationships = schema?.relationships?.filter((relationship) => relationship.kind !== "Attribute") ?? [];
  const tabs = [
    {
      label: schema.label,
      name: schema.label
    },
    ...otherRelationships.map((relationship) => ({ label: relationship.label, name: relationship.name}))
  ];

  const navigate = useNavigate();

  const navigateToObjectEditPage = () => {
    navigate(`/objects/${objectname}/${objectid}/edit`);
  };

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
    <div className="bg-white flex-1 overflow-auto">
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
            <Button onClick={navigateToObjectEditPage} className="mr-4">
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
                <dt className="text-sm font-medium text-gray-500">ID</dt>
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
                        <dt className="text-sm font-medium text-gray-500">
                          {attribute.label}
                        </dt>

                        <div className="flex items-center">
                          <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0">
                            {(objectDetails[attribute.name]?.value !== false && objectDetails[attribute.name].value) ? objectDetails[attribute.name].value : "-"}
                            {objectDetails[attribute.name]?.value === true && (<CheckIcon className="h-4 w-4" />)}
                            {objectDetails[attribute.name]?.value === false && (<XMarkIcon className="h-4 w-4" />)}
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
                              ]} />
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
                  (relationshipSchema: any) => <RelationshipDetails key={relationshipSchema.name} relationshipsData={objectDetails[relationshipSchema.name]} relationshipSchema={relationshipSchema} />
                )
              }
            </dl>
          </div>
        )
      }

      {
        qspTab
        && (
          <RelationshipsDetails />
        )
      }
    </div>
  );
}
