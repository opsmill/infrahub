import { EyeSlashIcon, LockClosedIcon, PencilSquareIcon, PlusIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Link } from "../../components/link";
import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import { RoundedButton } from "../../components/rounded-button";
import { SelectOption } from "../../components/select";
import SlideOver from "../../components/slide-over";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getAttributeColumnsFromNodeOrGenericSchema } from "../../utils/getSchemaObjectColumns";
import updateObjectWithId from "../../utils/updateObjectWithId";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import NoDataFound from "../no-data-found/no-data-found";
import { constructPath } from "../../utils/fetch";
import { getObjectDetailsUrl } from "../../utils/objects";
import { BUTTON_TYPES, Button } from "../../components/button";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";
import { classNames } from "../../utils/common";

type iRelationDetailsProps = {
  parentNode: any;
  parentSchema: iNodeSchema;
  refreshObject: Function;
  relationshipsData: any;
  relationshipSchema: any;
  mode: "TABLE" | "DESCRIPTION-LIST";
}

export default function RelationshipDetails(props: iRelationDetailsProps) {
  const {objectname, objectid} = useParams();
  const {relationshipsData, relationshipSchema, refreshObject} = props;
  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const [showAddDrawer, setShowAddDrawer] = useState(false);
  const schema = schemaList.filter((s) => s.name === objectname)[0];
  const [showRelationMetaEditModal, setShowRelationMetaEditModal] = useState(false);
  const [rowForMetaEdit, setRowForMetaEdit] = useState();

  let options: SelectOption[] = [];

  const generic = generics.find(g => g.kind === relationshipSchema.peer);

  if(generic) {
    (generic.used_by || [])
    .forEach(name => {
      const relatedSchema = schemaList.find(s => s.kind === name);

      if(relatedSchema) {
        options.push({
          id: relatedSchema.name,
          name: name,
        });
      }
    });
  } else {
    const relatedSchema = schemaList.find(s => s.kind === relationshipSchema.peer);

    if(relatedSchema) {
      options.push({
        id: relatedSchema.name,
        name: relatedSchema.label ?? relatedSchema.name,
      });
    }
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

  const columns = getAttributeColumnsFromNodeOrGenericSchema(schemaList, generics, relationshipSchema.peer);

  if(!relationshipsData) {
    return null;
  }

  if(relationshipsData && relationshipsData._relation__is_visible === false) {
    return null;
  }

  if (relationshipSchema?.cardinality === "many" && !Array.isArray(relationshipsData)) {
    return null;
  }


  const handleDeleteRelationship = async (event: any, id: string) => {
    event.stopPropagation();

    const newList  = relationshipsData.map((item: any) => ({ id: item.id })).filter((item: any) =>  item.id !== id);

    await updateObjectWithId(
    objectid!,
    schema,
    {
      [relationshipSchema.name]: newList
    }
    );

    refreshObject();

    setShowAddDrawer(false);
  };

  return <>
    <div
      key={relationshipSchema?.name}
    >
      {
        relationshipsData
        && (
          <>
            {
              relationshipSchema?.cardinality === "one"
              && (
                <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    {relationshipSchema?.label}
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline flex items-center">
                    <Link
                      onClick={() => navigate(constructPath(getObjectDetailsUrl(relationshipsData, schemaKindName, relationshipsData.id)))}
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
                </div>
              )
            }

            {
              relationshipSchema?.cardinality === "many" && props.mode === "TABLE"
              && (
                <div className="mt-0 flex flex-col px-4 sm:px-6 lg:px-8 w-full overflow-x-auto flex-1">
                  <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
                    <div className="inline-block min-w-full pt-2 align-middle">
                      <div className="shadow-sm ring-1 ring-black ring-opacity-5">
                        <table
                          className="min-w-full border-separate"
                          style={{ borderSpacing: 0 }}
                        >
                          <thead className="bg-gray-50">
                            <tr>
                              {
                                columns
                                ?.map(
                                  (column) => (
                                    <th
                                      key={column.name}
                                      scope="col"
                                      className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 py-3.5 pl-4 pr-3 text-left text-sm font-semibold text-gray-900 backdrop-blur backdrop-filter sm:pl-6 lg:pl-8"
                                    >
                                      {column.label}
                                    </th>
                                  )
                                )
                              }
                              <th scope="col" className="relative py-3.5 pl-3 w-24">
                                <span className="sr-only">Meta</span>
                              </th>
                              <th scope="col" className="relative py-3.5 pl-3 w-24">
                                <span className="sr-only">Delete</span>
                              </th>
                            </tr>
                          </thead>
                          <tbody className="bg-white">
                            {
                              relationshipsData
                              ?.map(
                                (row: any, index: number) => (
                                  <tr
                                    onClick={() => navigate(getObjectDetailsUrl(row, schemaKindName, row.id))}
                                    key={index}
                                    className="hover:bg-gray-50 cursor-pointer"
                                  >
                                    {columns?.map((column) => (
                                      <td
                                        key={row.id + "-" + column.name}
                                        className={classNames(
                                          index !== relationshipsData.length - 1
                                            ? "border-b border-gray-200"
                                            : "",
                                          "whitespace-nowrap py-4 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                                        )}
                                      >
                                        {getObjectItemDisplayValue(row, column)}
                                      </td>
                                    ))}
                                    <td className="relative py-4 px-5 text-right text-sm font-medium w-24">
                                      <Button onClick={(event: any) => {
                                        event.stopPropagation();
                                        setRowForMetaEdit(row);
                                        setShowRelationMetaEditModal(true);
                                      }}>
                                        Meta
                                      </Button>
                                    </td>
                                    <td className="relative py-4 px-5 text-right text-sm font-medium w-24">
                                      <Button buttonType={BUTTON_TYPES.CANCEL} onClick={(event: any) => handleDeleteRelationship(event, row.id)}>
                                        Delete
                                      </Button>
                                    </td>
                                  </tr>
                                )
                              )
                            }
                          </tbody>
                        </table>

                        {
                          relationshipsData && !relationshipsData.length && <NoDataFound />
                        }
                      </div>
                    </div>
                  </div>
                </div>
              )}

            {
              relationshipSchema?.cardinality === "many" && props.mode === "DESCRIPTION-LIST"
              && (
                <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6">
                  <dt className="text-sm font-medium text-gray-500 flex items-center">
                    {relationshipSchema?.label}
                  </dt>
                  <dl className="sm:divide-y sm:divide-gray-200">
                    <div className="sm:col-span-2 space-y-4">
                      {relationshipsData.length === 0 && "-"}
                      {
                        relationshipsData?.map(
                          (item: any) => (
                            <dd
                              className="mt-1 text-sm text-gray-900 sm:mt-0 underline flex items-center"
                              key={item.id}
                            >
                              <Link onClick={() => navigate(constructPath(getObjectDetailsUrl(item, schemaKindName, item.id)))}>
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
                              {/* {<TrashIcon className="h-5 w-5 ml-2" onClick={async () => {
                            const newList  = relationshipsData.map((row: any) => ({ id: row.id })).filter((row: any) =>  row.id !== item.id);
                            await updateObjectWithId(objectid!, schema, {
                              [relationshipSchema.name]: newList
                            });
                            props.refreshObject();
                            setShowAddDrawer(false);
                          }}/>} */}
                            </dd>
                          )
                        )}
                    </div>
                  </dl>
                </div>
              )}
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
      <SlideOver title={`Add ${relationshipSchema.label}`} subtitle={"Add"} open={showAddDrawer} setOpen={setShowAddDrawer}>
        <EditFormHookComponent onCancel={() => {
          setShowAddDrawer(false);
        }} onSubmit={async (data) => {
          if(data?.id) {
            const newList  = [...relationshipsData.map((row: any) => ({ id: row.id })), { id: data.id }];
            await updateObjectWithId(objectid!, schema, {
              [relationshipSchema.name]: newList
            });
            props.refreshObject();
            setShowAddDrawer(false);
          }
        }} fields={formFields} />
      </SlideOver>
      <SlideOver title={"Meta-details"} subtitle="Update meta details" open={showRelationMetaEditModal} setOpen={setShowRelationMetaEditModal}>
        <ObjectItemMetaEdit closeDrawer={() => {
          setShowRelationMetaEditModal(false);
        }}  onUpdateComplete={() => {
          setShowRelationMetaEditModal(false);
          props.refreshObject();
        }} attributeOrRelationshipToEdit={rowForMetaEdit} schemaList={schemaList} schema={schema} attributeOrRelationshipName={relationshipSchema.name} type="relationship" row={{...props.parentNode, [relationshipSchema.name]: relationshipsData}}  />
      </SlideOver>
    </div>
  </>;
};