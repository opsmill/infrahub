import { EyeSlashIcon, LockClosedIcon, PencilSquareIcon, PlusIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { HasNameAndID } from "../../components-form/select";
import { Link } from "../../components/link";
import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import { RoundedButton } from "../../components/rounded-button";
import SlideOver from "../../components/slide-over";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { iSchemaKindNameMap, schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import updateObjectWithId from "../../utils/updateObjectWithId";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";

type iRelationDetailsProps = {
  parentSchema: iNodeSchema;
  refreshObject: Function;
  relationshipsData: any;
  relationshipSchema: any;
}

const regex = /^Related/; // starts with Related

const getObjectDetailsUrl = (relationshipsData: {__typename: string}, schemaKindName: iSchemaKindNameMap, relatedNodeId: string) :string => {
  const peerKind: string = relationshipsData?.__typename?.replace(regex, "");
  const peerName = schemaKindName[peerKind];
  const url = `/objects/${peerName}/${relatedNodeId}`;
  return url;
};

export default function RelationshipDetails(props: iRelationDetailsProps) {
  const { objectname, objectid } = useParams();
  const { relationshipsData, relationshipSchema } = props;
  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const [showAddDrawer, setShowAddDrawer] = useState(false);
  const schema = schemaList.filter((s) => s.name === objectname)[0];

  let options: HasNameAndID[] = [];

  const generic = generics.find(g => g.kind === relationshipSchema.peer);
  if(generic) {
    (generic.used_by || []).forEach(name => {
      const relatedSchema = schemaList.find(s => s.kind === name);
      if(relatedSchema) {
        options.push({
          id: relatedSchema.name,
          name: name,
        });
      }
    });
  }

  const formFields: DynamicFieldData[] = [
    {
      kind: "Text",
      label: relationshipSchema.label,
      name: "id",
      options: {
        values: options,
      },
      type: "select2step",
      value: {},
      config: {},
    }
  ];

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
      className="flex-1"
      key={relationshipSchema?.name}
    >
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
                <div className="py-3 flow-root">
                  <div className="px-4 sm:px-6 lg:px-8">
                    <table className="w-full text-left">
                      <thead className="bg-white">
                        <tr>
                          <th scope="col" className="relative isolate py-3.5 pr-3 text-left text-sm font-semibold text-gray-900">
                            Name
                            <div className="absolute inset-y-0 right-full -z-10 w-screen border-b border-b-gray-200" />
                            <div className="absolute inset-y-0 left-0 -z-10 w-screen border-b border-b-gray-200" />
                          </th>
                          <th
                            scope="col"
                            className="hidden px-3 py-3.5 text-left text-sm font-semibold text-gray-900 sm:table-cell"
                          >
                            Kind
                          </th>
                          <th
                            scope="col"
                            className="hidden px-3 py-3.5 text-left text-sm font-semibold text-gray-900 md:table-cell"
                          >
                            Protected
                          </th>
                          <th scope="col" className="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">
                            Info
                          </th>
                          <th scope="col" className="relative py-3.5 pl-3 w-20">
                            <span className="sr-only">Show</span>
                          </th>
                          <th scope="col" className="relative py-3.5 pl-3 w-20">
                            <span className="sr-only">Edit</span>
                          </th>
                          <th scope="col" className="relative py-3.5 pl-3 w-24">
                            <span className="sr-only">Delete</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {relationshipsData?.map((item: any) => (
                          <tr key={item.id}>
                            <td className="relative py-4 pr-3 text-sm font-medium text-gray-900">
                              {item.display_label}
                              <div className="absolute bottom-0 right-full h-px w-screen bg-gray-100" />
                              <div className="absolute bottom-0 left-0 h-px w-screen bg-gray-100" />
                            </td>
                            <td className="hidden px-3 py-4 text-sm text-gray-500 sm:table-cell">{item.__typename.replace(regex, "")}</td>
                            <td className="hidden px-1 py-4 text-sm text-gray-500 md:table-cell">{
                              item._relation__is_protected
                            && (
                              <LockClosedIcon className="h-5 w-5 ml-2" />
                            )
                            }

                            </td>
                            <td className="px-1 py-4 text-sm text-gray-500">
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
                            </td>
                            <td className="relative py-4 pl-3 text-right text-sm font-medium w-20">
                              <div className="text-indigo-600 hover:text-indigo-900 cursor-pointer">
                                Show
                              </div>
                            </td>
                            <td className="relative py-4 pl-3 text-right text-sm font-medium w-20">
                              <div className="text-indigo-600 hover:text-indigo-900 cursor-pointer">
                                Edit
                              </div>
                            </td>
                            <td className="relative py-4 pl-3 text-right text-sm font-medium w-24">
                              <div className="text-indigo-600 hover:text-indigo-900 cursor-pointer" onClick={async () => {
                                const newList  = relationshipsData.map((row: any) => ({ id: row.id })).filter((row: any) =>  row.id !== item.id);
                                await updateObjectWithId(objectid!, schema, {
                                  [relationshipSchema.name]: newList
                                });
                                props.refreshObject();
                                setShowAddDrawer(false);
                              }}>
                                Delete
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

            {/* {
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
                            {item.display_label} {item.__typename}
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
                          {<TrashIcon className="h-5 w-5 ml-2" onClick={async () => {
                            const newList  = relationshipsData.map((row: any) => ({ id: row.id })).filter((row: any) =>  row.id !== item.id);
                            await updateObjectWithId(objectid!, schema, {
                              [relationshipSchema.name]: newList
                            });
                            props.refreshObject();
                            setShowAddDrawer(false);
                          }}/>}
                        </dd>
                      )
                    )}
                </div>
              )} */}
          </>
        )}
      <div className="absolute bottom-4 right-4">
        <RoundedButton onClick={() => setShowAddDrawer(true)} className="p-3 ml-2 bg-blue-500 text-sm hover:bg-blue-600 focus:ring-blue-500 focus:ring-offset-gray-50 focus:ring-offset-2">
          <PlusIcon
            className="h-7 w-7 text-white"
            aria-hidden="true"
          />
        </RoundedButton>
      </div>
      {!relationshipsData && <>-</>}
      <SlideOver title={`Add ${relationshipSchema.label}`} subtitle={"Add"} open={showAddDrawer} setOpen={setShowAddDrawer}>
        <EditFormHookComponent onCancel={() => {
          console.log("Cancelled");
          setShowAddDrawer(false);
        }} onSubmit={async (data) => {
          console.log("Submit: ", data);
          if(data?.id) {
            const newList  = [...relationshipsData.map((row: any) => ({ id: row.id })), { id: data.id }];
            console.log({
              newList,
            });
            await updateObjectWithId(objectid!, schema, {
              [relationshipSchema.name]: newList
            });
            props.refreshObject();
            setShowAddDrawer(false);
          }
        }} fields={formFields} />
      </SlideOver>
    </div>
  </>;
};