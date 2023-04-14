import { EyeSlashIcon, LockClosedIcon, PencilSquareIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { iSchemaKindNameMap, schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { Link } from "../../components/link";
import { useNavigate } from "react-router-dom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";

type iRelationDetailsProps = {
  relationshipsData: any;
  relationshipSchema: any;
}

const getObjectDetailsUrl = (relationshipsData: {__typename: string}, schemaKindName: iSchemaKindNameMap, relatedNodeId: string) :string => {
  const regex = /^Related/; // starts with Related
  const peerKind: string = relationshipsData?.__typename?.replace(regex, "");
  const peerName = schemaKindName[peerKind];
  const url = `/objects/${peerName}/${relatedNodeId}`;
  return url;
};

export default function RelationshipDetails(props: iRelationDetailsProps) {
  const { relationshipsData, relationshipSchema } = props;

  const [schemaKindName] = useAtom(schemaKindNameState);
  const navigate = useNavigate();

  const [, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  if(relationshipsData && relationshipsData._relation__is_visible === false) {
    return null;
  }

  if (relationshipSchema?.cardinality === "many" && !Array.isArray(relationshipsData)) {
    return null;
  }

  return <>
    <div
      className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-5 sm:px-6"
      key={relationshipSchema?.name}
    >
      <dt className="text-sm font-medium text-gray-500">
        {relationshipSchema?.label}
      </dt>
      {
        relationshipsData
        && (
          <>
            {
              relationshipSchema?.cardinality === "one"
              && (
                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline flex items-center">
                  <Link
                    onClick={() => navigate(getObjectDetailsUrl(relationshipsData, schemaKindName, relationshipsData.id))}
                  >
                    {relationshipsData.display_label}
                  </Link>

                  {relationshipsData && (
                    <MetaDetailsTooltip items={[
                      {
                        label: "Updated at",
                        value: relationshipsData._updated_at,
                        type: "date",
                      },
                      {
                        label: "Update time",
                        value: `${new Date(relationshipsData._updated_at).toLocaleDateString()} ${new Date(relationshipsData._updated_at).toLocaleTimeString()}`,
                        type: "text",
                      },
                      {
                        label: "Source",
                        value: relationshipsData._relation__source,
                        type: "link"
                      },
                      {
                        label: "Owner",
                        value: relationshipsData._relation__owner,
                        type: "link"
                      },
                      {
                        label: "Is protected",
                        value: relationshipsData._relation__is_protected ? "True" : "False",
                        type: "text"
                      },
                    ]}
                    header={(<div className="flex justify-between w-full py-4">
                      <div className="font-semibold">{relationshipSchema.label}</div>
                      <div className="cursor-pointer" onClick={() => {
                        setMetaEditFieldDetails({
                          type: "relationship",
                          attributeOrRelationshipName: relationshipSchema.name,
                        });
                        setShowMetaEditModal(true);
                      }}>
                        <PencilSquareIcon className="w-5 h-5 text-blue-500" />
                      </div>
                    </div>
                    )}
                    />
                  )}

                  {
                    relationshipsData._relation__is_protected
                    && (
                      <LockClosedIcon className="h-5 w-5 ml-2" />
                    )
                  }

                  {
                    relationshipsData._relation__is_visible === false
                    && (
                      <EyeSlashIcon className="h-5 w-5 ml-2" />
                    )
                  }
                </dd>
              )
            }

            {
              relationshipSchema?.cardinality === "many"
              && (
                <div className="sm:col-span-2 space-y-4">
                  {
                    relationshipsData?.map(
                      (item: any) => (
                        <dd
                          className="mt-1 text-sm text-gray-900 sm:mt-0 underline flex items-center"
                          key={item.id}
                        >
                          <Link onClick={() => navigate(getObjectDetailsUrl(item, schemaKindName, item.id))}>
                            {item.display_label}
                          </Link>

                          {
                            item
                            && (
                              <MetaDetailsTooltip items={[
                                {
                                  label: "Updated at",
                                  value: item._updated_at,
                                  type: "date",
                                },
                                {
                                  label: "Update time",
                                  value: `${new Date(item._updated_at).toLocaleDateString()} ${new Date(item._updated_at).toLocaleTimeString()}`,
                                  type: "text",
                                },
                                {
                                  label: "Source",
                                  value: item._relation__source,
                                  type: "link"
                                },
                                {
                                  label: "Owner",
                                  value: item._relation__owner,
                                  type: "link"
                                },
                                {
                                  label: "Is protected",
                                  value: item._relation__is_protected ? "True" : "False",
                                  type: "text"
                                },
                              ]} />
                            )
                          }

                          {
                            item._relation__is_protected
                            && (
                              <LockClosedIcon className="h-5 w-5 ml-2" />
                            )
                          }

                          {
                            item._relation__is_visible === false
                            && (
                              <EyeSlashIcon className="h-5 w-5 ml-2" />
                            )
                          }
                        </dd>
                      )
                    )}
                </div>
              )}
          </>
        )}
      {!relationshipsData && <>-</>}
    </div>
  </>;
};