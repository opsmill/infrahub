import { gql, useReactiveVar } from "@apollo/client";
import {
  EyeSlashIcon,
  LockClosedIcon,
  PencilSquareIcon,
  PlusIcon,
  Square3Stack3DIcon,
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../../components/alert";
import { BUTTON_TYPES, Button } from "../../components/button";
import { Link } from "../../components/link";
import MetaDetailsTooltip from "../../components/meta-details-tooltips";
import ModalDelete from "../../components/modal-delete";
import { RoundedButton } from "../../components/rounded-button";
import { SelectOption } from "../../components/select";
import SlideOver from "../../components/slide-over";
import { DEFAULT_BRANCH_NAME } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { branchVar } from "../../graphql/variables/branchVar";
import { dateVar } from "../../graphql/variables/dateVar";
// import { ReactComponent as UnlinkIcon } from "../../images/icons/unlink.svg";
import { AuthContext } from "../../decorators/withAuth";
import { addRelationship } from "../../graphql/mutations/relationships/addRelationship";
import UnlinkIcon from "../../images/icons/unlink.svg";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getAttributeColumnsFromNodeOrGenericSchema } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "../../utils/objects";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";

type iRelationDetailsProps = {
  parentNode: any;
  parentSchema: iNodeSchema;
  relationshipsData: any;
  relationshipSchema: any;
  mode: "TABLE" | "DESCRIPTION-LIST";
  refetch?: Function;
  onDeleteRelationship?: Function;
};

const regex = /^Related/; // starts with Related

export default function RelationshipDetails(props: iRelationDetailsProps) {
  const { mode, relationshipsData, relationshipSchema, refetch, onDeleteRelationship } = props;

  const { objectname, objectid } = useParams();
  const auth = useContext(AuthContext);

  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const branch = useReactiveVar(branchVar);
  const date = useReactiveVar(dateVar);
  const [showAddDrawer, setShowAddDrawer] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showRelationMetaEditModal, setShowRelationMetaEditModal] = useState(false);
  const [rowForMetaEdit, setRowForMetaEdit] = useState<any>();
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<any>();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState<any>();

  const schema = schemaList.find((s) => s.kind === objectname);

  let options: SelectOption[] = [];

  const generic = generics.find((g) => g.kind === relationshipSchema.peer);

  if (generic) {
    (generic.used_by || []).forEach((kind) => {
      const relatedSchema = schemaList.find((s) => s.kind === kind);

      if (relatedSchema) {
        options.push({
          id: relatedSchema.kind,
          name: relatedSchema.name,
        });
      }
    });
  } else {
    const relatedSchema = schemaList.find((s) => s.kind === relationshipSchema.peer);

    if (relatedSchema) {
      options.push({
        id: relatedSchema.kind,
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
    },
  ];

  const [schemaKindName] = useAtom(schemaKindNameState);
  const navigate = useNavigate();

  const [, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const columns = getAttributeColumnsFromNodeOrGenericSchema(
    schemaList,
    generics,
    relationshipSchema.peer
  );

  if (relationshipsData && relationshipsData?.properties?.is_visible === false) {
    return null;
  }

  if (relationshipSchema?.cardinality === "many" && !Array.isArray(relationshipsData)) {
    return null;
  }

  const handleDeleteRelationship = async (id: string) => {
    if (onDeleteRelationship) {
      await onDeleteRelationship(id);

      setShowAddDrawer(false);

      setRelatedRowToDelete(undefined);

      return;
    }

    const newList = relationshipsData
      .map((item: any) => ({ id: item.id }))
      .filter((item: any) => item.id !== id);

    const mutationString = updateObjectWithId({
      name: schema.name,
      data: stringifyWithoutQuotes({
        id: objectid,
        [relationshipSchema.name]: newList,
      }),
    });

    const mutation = gql`
      ${mutationString}
    `;

    await graphqlClient.mutate({
      mutation,
      context: { branch: branch?.name, date },
    });

    setShowAddDrawer(false);

    setRelatedRowToDelete(undefined);

    if (refetch) {
      refetch();
    }

    toast(
      <Alert
        type={ALERT_TYPES.SUCCESS}
        message={`Association with ${relationshipSchema.peer} removed`}
      />
    );
  };

  const handleSubmit = async (data: any) => {
    if (data?.id) {
      setIsLoading(true);

      const mutationString = addRelationship({
        data: stringifyWithoutQuotes({
          id: objectid,
          name: relationshipSchema.name,
          nodes: [data],
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      if (refetch) {
        refetch();
      }

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Association with ${relationshipSchema.peer} added`}
        />
      );

      setIsLoading(false);

      setShowAddDrawer(false);

      refetch && refetch();
    }
  };

  // TODO: Refactor reltionships components to compute the correct columns
  const defaultColumns = [
    { label: "Type", name: "__typename" },
    { label: "Name", name: "display_label" },
  ];

  const newColumns = columns?.length ? columns : defaultColumns;

  return (
    <>
      <div key={relationshipSchema?.name}>
        {!relationshipsData && (
          <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-4 sm:px-6">
            <dt className="text-sm font-medium text-gray-500 flex items-center">
              {relationshipSchema?.label}
            </dt>
            <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 flex items-center">
              -
            </dd>
          </div>
        )}
        {relationshipsData && (
          <>
            {relationshipSchema?.cardinality === "one" && (
              <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6">
                <dt className="text-sm font-medium text-gray-500 flex items-center">
                  {relationshipSchema?.label}
                </dt>
                <dd className="mt-1 text-sm text-gray-900 sm:col-span-2 sm:mt-0 underline flex items-center">
                  <Link
                    onClick={() =>
                      navigate(
                        constructPath(
                          getObjectDetailsUrl(
                            relationshipsData.node.id,
                            relationshipsData.node.__typename
                          )
                        )
                      )
                    }>
                    {relationshipsData.node?.display_label}
                  </Link>

                  {relationshipsData.properties && (
                    <div className="p-2">
                      <MetaDetailsTooltip
                        items={[
                          {
                            label: "Updated at",
                            value: relationshipsData.properties.updated_at,
                            type: "date",
                          },
                          {
                            label: "Update time",
                            value: `${new Date(
                              relationshipsData.properties.updated_at
                            ).toLocaleDateString()} ${new Date(
                              relationshipsData.properties.updated_at
                            ).toLocaleTimeString()}`,
                            type: "text",
                          },
                          {
                            label: "Source",
                            value: relationshipsData.properties.source,
                            type: "link",
                          },
                          {
                            label: "Owner",
                            value: relationshipsData.properties.owner,
                            type: "link",
                          },
                          {
                            label: "Is protected",
                            value: relationshipsData.properties.is_protected ? "True" : "False",
                            type: "text",
                          },
                        ]}
                        header={
                          <div className="flex justify-between w-full py-4">
                            <div className="font-semibold">{relationshipSchema.label}</div>
                            <div
                              className="cursor-pointer"
                              onClick={() => {
                                setMetaEditFieldDetails({
                                  type: "relationship",
                                  attributeOrRelationshipName: relationshipSchema.name,
                                  label: relationshipSchema.label || relationshipSchema.name,
                                });
                                setShowMetaEditModal(true);
                              }}>
                              <PencilSquareIcon className="w-5 h-5 text-custom-blue-500" />
                            </div>
                          </div>
                        }
                      />
                    </div>
                  )}

                  {relationshipsData.properties?.is_protected && (
                    <LockClosedIcon className="h-5 w-5 ml-2" />
                  )}

                  {relationshipsData.properties?.is_visible === false && (
                    <EyeSlashIcon className="h-5 w-5 ml-2" />
                  )}
                </dd>
              </div>
            )}

            {relationshipSchema?.cardinality === "many" && mode === "TABLE" && (
              <div className="mt-0 flex flex-col px-4 sm:px-6 lg:px-8 w-full flex-1">
                <div className="-my-2 -mx-4 sm:-mx-6 lg:-mx-8">
                  <div className="inline-block min-w-full pt-2 align-middle">
                    <div className="shadow-sm ring-1 ring-custom-black ring-opacity-5 overflow-x-auto">
                      <table className="min-w-full border-separate" style={{ borderSpacing: 0 }}>
                        <thead className="bg-gray-50">
                          <tr>
                            {newColumns?.map((column) => (
                              <th
                                key={column.name}
                                scope="col"
                                className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 px-4 py-2 text-left text-xs font-semibold text-gray-900 backdrop-blur backdrop-filter">
                                {column.label}
                              </th>
                            ))}
                            <th
                              scope="col"
                              className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 px-4 py-2 text-left text-xs font-semibold text-gray-900 backdrop-blur backdrop-filter">
                              <span className="sr-only">Meta</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-custom-white">
                          {relationshipsData?.map(({ node, properties }: any, index: number) => (
                            <tr
                              onClick={() =>
                                navigate(getObjectDetailsUrl(node.id, node.__typename))
                              }
                              key={index}
                              className="hover:bg-gray-50 cursor-pointer">
                              {newColumns?.map((column) => (
                                <td
                                  key={node.id + "-" + column.name}
                                  className={classNames(
                                    index !== relationshipsData.length - 1
                                      ? "border-b border-gray-200"
                                      : "",
                                    "whitespace-nowrap py-3 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                                  )}>
                                  {getObjectItemDisplayValue(node, column)}
                                </td>
                              ))}
                              <td
                                className={classNames(
                                  index !== relationshipsData.length - 1
                                    ? "border-b border-gray-200"
                                    : "",
                                  "whitespace-nowrap py-3 pl-4 pr-3 text-sm font-medium text-gray-900 sm:pl-6 lg:pl-8"
                                )}>
                                <div
                                  className="p-2"
                                  onClick={() => {
                                    setRowForMetaEdit(node);
                                    setShowRelationMetaEditModal(true);
                                  }}>
                                  <MetaDetailsTooltip
                                    position="LEFT"
                                    items={[
                                      {
                                        label: "Updated at",
                                        value: properties?.updated_at,
                                        type: "date",
                                      },
                                      {
                                        label: "Update time",
                                        value: `${new Date(
                                          properties?.updated_at
                                        ).toLocaleDateString()} ${new Date(
                                          properties?.updated_at
                                        ).toLocaleTimeString()}`,
                                        type: "text",
                                      },
                                      {
                                        label: "Source",
                                        value: properties?.source?.display_label,
                                        type: "link",
                                      },
                                      {
                                        label: "Owner",
                                        value: properties?.owner?.display_label,
                                        type: "link",
                                      },
                                      {
                                        label: "Is protected",
                                        value: properties?.is_protected ? "True" : "False",
                                        type: "text",
                                      },
                                    ]}
                                  />
                                </div>

                                <Button
                                  disabled={!auth?.permissions?.write}
                                  buttonType={BUTTON_TYPES.INVISIBLE}
                                  onClick={() => {
                                    setRelatedObjectToEdit(node);
                                  }}>
                                  <PencilSquareIcon className="w-6 h-6 text-gray-500" />
                                </Button>

                                <Button
                                  disabled={!auth?.permissions?.write}
                                  buttonType={BUTTON_TYPES.INVISIBLE}
                                  onClick={() => {
                                    setRelatedRowToDelete(node);
                                  }}>
                                  <img src={UnlinkIcon} className="w-6 h-6" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>

                      {relationshipsData && !relationshipsData.length && (
                        <NoDataFound message="No relationship found." />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {relationshipSchema?.cardinality === "many" && mode === "DESCRIPTION-LIST" && (
              <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-3 sm:px-6">
                <dt className="text-sm font-medium text-gray-500 flex items-center">
                  {relationshipSchema?.label}
                </dt>
                <dl className="sm:divide-y sm:divide-gray-200">
                  <div className="sm:col-span-2 space-y-4">
                    {relationshipsData?.length === 0 && "-"}
                    {relationshipsData?.map(({ node, properties }: any) => (
                      <dd
                        className="mt-1 text-sm text-gray-900 sm:mt-0 underline flex items-center"
                        key={node.id}>
                        <Link
                          onClick={() =>
                            navigate(constructPath(getObjectDetailsUrl(node.id, node.__typename)))
                          }>
                          {node.display_label}
                        </Link>

                        {node && (
                          <div className="p-2">
                            <MetaDetailsTooltip
                              items={[
                                {
                                  label: "Updated at",
                                  value: properties.updated_at,
                                  type: "date",
                                },
                                {
                                  label: "Update time",
                                  value: `${new Date(
                                    properties.updated_at
                                  ).toLocaleDateString()} ${new Date(
                                    properties.updated_at
                                  ).toLocaleTimeString()}`,
                                  type: "text",
                                },
                                {
                                  label: "Source",
                                  value: properties._relation__source,
                                  type: "link",
                                },
                                {
                                  label: "Owner",
                                  value: properties.owner?.display_label,
                                  type: "link",
                                },
                                {
                                  label: "Is protected",
                                  value: properties.is_protected ? "True" : "False",
                                  type: "text",
                                },
                              ]}
                            />
                          </div>
                        )}

                        {properties.is_protected && <LockClosedIcon className="h-5 w-5 ml-2" />}

                        {properties.is_visible === false && (
                          <EyeSlashIcon className="h-5 w-5 ml-2" />
                        )}
                        {/* {<TrashIcon className="h-5 w-5 ml-2" onClick={async () => {
                            const newList  = relationshipsData.map((row: any) => ({ id: row.id })).filter((row: any) =>  row.id !== item.id);
                            await updateObjectWithId(objectid!, schema, {
                              [relationshipSchema.name]: newList
                            });
                            props.refreshObject();
                            setShowAddDrawer(false);
                          }}/>} */}
                      </dd>
                    ))}
                  </div>
                </dl>
              </div>
            )}
          </>
        )}

        {mode === "TABLE" && (
          <div className="absolute bottom-4 right-4 z-10">
            <RoundedButton
              disabled={!auth?.permissions?.write}
              onClick={() => setShowAddDrawer(true)}
              className="p-3 ml-2 bg-custom-blue-500 text-sm hover:bg-custom-blue-500 focus:ring-custom-blue-500 focus:ring-offset-gray-50 focus:ring-offset-2">
              <PlusIcon className="h-7 w-7 text-custom-white" aria-hidden="true" />
            </RoundedButton>
          </div>
        )}

        <SlideOver
          title={
            <div className="space-y-2">
              <div className="flex items-center w-full">
                <span className="text-lg font-semibold mr-3">
                  Add associated {relationshipSchema.label}
                </span>
                <div className="flex-1"></div>
                <div className="flex items-center">
                  <Square3Stack3DIcon className="w-5 h-5" />
                  <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                </div>
              </div>
              <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
                <svg
                  className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                  viewBox="0 0 6 6"
                  aria-hidden="true">
                  <circle cx={3} cy={3} r={3} />
                </svg>
                {relationshipSchema.peer}
              </span>
            </div>
          }
          open={showAddDrawer}
          setOpen={setShowAddDrawer}>
          <EditFormHookComponent
            onCancel={() => {
              setShowAddDrawer(false);
            }}
            onSubmit={handleSubmit}
            fields={formFields}
            isLoading={isLoading}
          />
        </SlideOver>
        <SlideOver
          title={
            <>
              {rowForMetaEdit && (
                <div className="space-y-2">
                  <div className="flex items-center w-full">
                    <span className="text-lg font-semibold mr-3">
                      {props.parentNode?.display_label} - {rowForMetaEdit.display_label}
                    </span>
                    <div className="flex-1"></div>
                    <div className="flex items-center">
                      <Square3Stack3DIcon className="w-5 h-5" />
                      <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                    </div>
                  </div>
                  <div className="text-gray-500">Association metadata</div>
                </div>
              )}
            </>
          }
          open={showRelationMetaEditModal}
          setOpen={setShowRelationMetaEditModal}>
          <ObjectItemMetaEdit
            closeDrawer={() => {
              setShowRelationMetaEditModal(false);
            }}
            onUpdateComplete={() => setShowRelationMetaEditModal(false)}
            attributeOrRelationshipToEdit={rowForMetaEdit}
            schemaList={schemaList}
            schema={schema}
            attributeOrRelationshipName={relationshipSchema.name}
            type="relationship"
            row={{
              ...props.parentNode,
              [relationshipSchema.name]: relationshipsData,
            }}
          />
        </SlideOver>
        {relatedRowToDelete && (
          <ModalDelete
            title="Delete"
            description={
              <>
                Are you sure you want to remove the association between{" "}
                <b>`{props.parentNode.display_label}`</b> and{" "}
                <b>`{relatedRowToDelete.display_label}`</b>? The{" "}
                <b>`{relatedRowToDelete.__typename.replace(regex, "")}`</b>{" "}
                <b>`{relatedRowToDelete.display_label}`</b> won&apos;t be deleted in the process.
              </>
            }
            onCancel={() => setRelatedRowToDelete(undefined)}
            onDelete={() => {
              if (relatedRowToDelete?.id) {
                handleDeleteRelationship(relatedRowToDelete.id);
              }
            }}
            open={!!relatedRowToDelete}
            setOpen={() => setRelatedRowToDelete(undefined)}
          />
        )}
        {relatedObjectToEdit && (
          <SlideOver
            title={
              <>
                {
                  <div className="space-y-2">
                    <div className="flex items-center w-full">
                      <span className="text-lg font-semibold mr-3">
                        {relatedObjectToEdit?.display_label}
                      </span>
                      <div className="flex-1"></div>
                      <div className="flex items-center">
                        <Square3Stack3DIcon className="w-5 h-5" />
                        <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                      </div>
                    </div>
                    <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
                      <svg
                        className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                        viewBox="0 0 6 6"
                        aria-hidden="true">
                        <circle cx={3} cy={3} r={3} />
                      </svg>
                      {relatedObjectToEdit?.__typename.replace(regex, "")}
                    </span>
                  </div>
                }
              </>
            }
            open={!!relatedObjectToEdit}
            setOpen={() => setRelatedObjectToEdit(undefined)}>
            <ObjectItemEditComponent
              closeDrawer={() => {
                setRelatedObjectToEdit(undefined);
              }}
              onUpdateComplete={async () => {
                setRelatedObjectToEdit(undefined);
                if (refetch) {
                  refetch();
                }
              }}
              objectid={relatedObjectToEdit.id}
              objectname={(() => {
                const relatedKind = relatedObjectToEdit.__typename.replace(regex, "");
                const relatedSchema = schemaList.find((s) => s.kind === relatedKind);
                const kind = schemaKindName[relatedSchema!.kind];
                return kind;
              })()}
            />
          </SlideOver>
        )}
      </div>
    </>
  );
}
