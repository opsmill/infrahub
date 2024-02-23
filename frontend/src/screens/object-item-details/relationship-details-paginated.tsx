import { gql } from "@apollo/client";
import {
  EyeSlashIcon,
  LockClosedIcon,
  PencilSquareIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { BUTTON_TYPES, Button } from "../../components/buttons/button";
import { RoundedButton } from "../../components/buttons/rounded-button";
import MetaDetailsTooltip from "../../components/display/meta-details-tooltips";
import SlideOver from "../../components/display/slide-over";
import { SelectOption } from "../../components/inputs/select";
import ModalDelete from "../../components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { Link as StyledLink } from "../../components/utils/link";
import { DEFAULT_BRANCH_NAME } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useAuth } from "../../hooks/useAuth";
import { addRelationship } from "../../graphql/mutations/relationships/addRelationship";
import UnlinkIcon from "../../images/icons/unlink.svg";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { showMetaEditState } from "../../state/atoms/metaEditFieldDetails.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { metaEditFieldDetailsState } from "../../state/atoms/showMetaEdit.atom copy";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import { constructPath } from "../../utils/fetch";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getSchemaObjectColumns } from "../../utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "../../utils/objects";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import ObjectItemMetaEdit from "../object-item-meta-edit/object-item-meta-edit";
import { ObjectAttributeRow } from "./object-attribute-row";

type iRelationDetailsProps = {
  parentNode: any;
  relationshipsData: any;
  relationshipSchema: any;
  relationshipSchemaData: any;
  mode: "TABLE" | "DESCRIPTION-LIST";
  refetch?: Function;
  onDeleteRelationship?: Function;
};

const regex = /^Related/; // starts with Related

export default function RelationshipDetails(props: iRelationDetailsProps) {
  const {
    mode,
    relationshipsData,
    relationshipSchema,
    relationshipSchemaData,
    refetch,
    onDeleteRelationship,
  } = props;

  const { objectname, objectid } = useParams();
  const auth = useAuth();

  const [schemaList] = useAtom(schemaState);
  const [generics] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [showAddDrawer, setShowAddDrawer] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showRelationMetaEditModal, setShowRelationMetaEditModal] = useState(false);
  const [rowForMetaEdit, setRowForMetaEdit] = useState<any>();
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<any>();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState<any>();

  const parentSchema = schemaList.find((s) => s.kind === objectname);
  const generic = generics.find((g) => g.kind === relationshipSchemaData?.kind);
  const columns = getSchemaObjectColumns(relationshipSchemaData, mode === "TABLE");

  let options: SelectOption[] = [];

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
      options,
      type: "select2step",
      value: {},
      config: {},
    },
  ];

  const [, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  if (relationshipsData && relationshipsData?.properties?.is_visible === false) {
    return null;
  }

  if (relationshipSchema?.cardinality === "many" && !Array.isArray(relationshipsData)) {
    return null;
  }

  const handleDeleteRelationship = async (id: string) => {
    if (onDeleteRelationship) {
      await onDeleteRelationship(relationshipSchema.name, id);

      setShowAddDrawer(false);

      setRelatedRowToDelete(undefined);

      return;
    }

    const newList = relationshipsData
      .map((item: any) => ({ id: item.id }))
      .filter((item: any) => item.id !== id);

    const mutationString = updateObjectWithId({
      kind: parentSchema?.kind,
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
    }
  };

  // TODO: Refactor reltionships components to compute the correct columns
  const defaultColumns = [
    { label: "Type", name: "__typename" },
    { label: "Name", name: "display_label" },
  ];

  const newColumns = columns?.length ? columns : defaultColumns;

  return (
    <Fragment key={relationshipSchema?.name}>
      {!relationshipsData && <ObjectAttributeRow name={relationshipSchema?.label} value="-" />}

      {relationshipsData && (
        <>
          {relationshipSchema?.cardinality === "one" && (
            <ObjectAttributeRow
              name={relationshipSchema?.label}
              value={
                <>
                  <StyledLink
                    to={constructPath(
                      getObjectDetailsUrl(
                        relationshipsData.node?.id,
                        relationshipsData.node?.__typename
                      )
                    )}>
                    {relationshipsData.node?.display_label}
                  </StyledLink>

                  {relationshipsData.properties && (
                    <div className="px-2">
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
                          <div className="flex justify-between items-center w-full p-4">
                            <div className="font-semibold">{relationshipSchema.label}</div>
                            <Button
                              buttonType={BUTTON_TYPES.INVISIBLE}
                              disabled={!auth?.permissions?.write}
                              onClick={() => {
                                setMetaEditFieldDetails({
                                  type: "relationship",
                                  attributeOrRelationshipName: relationshipSchema.name,
                                  label: relationshipSchema.label || relationshipSchema.name,
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

                  {relationshipsData.properties?.is_protected && (
                    <LockClosedIcon className="w-4 h-4" />
                  )}

                  {relationshipsData.properties?.is_visible === false && (
                    <EyeSlashIcon className="w-4 h-4" />
                  )}
                </>
              }
            />
          )}

          {relationshipSchema?.cardinality === "many" && mode === "TABLE" && (
            <div className="flex-1 shadow-sm ring-1 ring-custom-black ring-opacity-5 overflow-x-auto">
              <table className="min-w-full border-separate" style={{ borderSpacing: 0 }}>
                <thead className="bg-gray-50">
                  <tr>
                    {newColumns?.map((column) => (
                      <th
                        key={column.name}
                        scope="col"
                        className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 p-2 text-left text-xs font-semibold text-gray-900">
                        {column.label}
                      </th>
                    ))}

                    <th
                      scope="col"
                      className="sticky top-0 border-b border-gray-300 bg-gray-50 bg-opacity-75 p-2 text-left text-xs font-semibold text-gray-900">
                      <span className="sr-only">Meta</span>
                    </th>
                  </tr>
                </thead>

                <tbody className="bg-custom-white">
                  {relationshipsData?.map(({ node, properties }: any, index: number) => (
                    <tr
                      key={index}
                      className="hover:bg-gray-50 cursor-pointer"
                      data-cy="relationship-row">
                      {newColumns?.map((column) => (
                        <td
                          key={node.id + "-" + column.name}
                          className={classNames(
                            index !== relationshipsData.length - 1
                              ? "border-b border-gray-200"
                              : "",
                            "whitespace-nowrap text-xs font-medium h-[36px]"
                          )}>
                          <Link
                            className="whitespace-wrap px-2 py-1 text-xs flex items-center text-gray-900"
                            to={constructPath(getObjectDetailsUrl(node.id, node.__typename))}>
                            {getObjectItemDisplayValue(node, column)}
                          </Link>
                        </td>
                      ))}

                      <td
                        className={classNames(
                          index !== relationshipsData.length - 1 ? "border-b border-gray-200" : "",
                          "whitespace-nowrap px-2 py-1 text-xs font-medium text-gray-900 flex justify-end"
                        )}>
                        <div
                          className="flex px-2"
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
                          }}
                          data-cy="metadata-edit-button">
                          <PencilSquareIcon className="w-4 h-4 text-gray-500" />
                        </Button>

                        <Button
                          disabled={!auth?.permissions?.write}
                          buttonType={BUTTON_TYPES.INVISIBLE}
                          onClick={() => {
                            setRelatedRowToDelete(node);
                          }}
                          data-cy="relationship-delete-button">
                          <img src={UnlinkIcon} className="w-4 h-4" />
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
          )}

          {relationshipSchema?.cardinality === "many" && mode === "DESCRIPTION-LIST" && (
            <ObjectAttributeRow
              name={relationshipSchema?.label}
              value={
                <dl className="flex flex-col">
                  {relationshipsData?.length === 0 && "-"}
                  {relationshipsData?.map(({ node, properties }: any) => (
                    <dd className="text-gray-900 underline flex items-center" key={node.id}>
                      <Link to={constructPath(getObjectDetailsUrl(node.id, node.__typename))}>
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

                      {properties.is_protected && <LockClosedIcon className="w-4 h-4" />}

                      {properties.is_visible === false && <EyeSlashIcon className="w-4 h-4" />}
                    </dd>
                  ))}
                </dl>
              }
            />
          )}
        </>
      )}

      {mode === "TABLE" && (
        <div className="absolute bottom-4 right-4 z-10">
          <RoundedButton
            disabled={!auth?.permissions?.write}
            onClick={() => setShowAddDrawer(true)}
            className="p-3 ml-2 bg-custom-blue-500 hover:bg-custom-blue-500 focus:ring-custom-blue-500 focus:ring-offset-gray-50 focus:ring-offset-2"
            data-cy="open-relationship-form-button">
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
                <Icon icon={"mdi:layers-triple"} />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
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
                    <Icon icon={"mdi:layers-triple"} />
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
          attributeOrRelationshipToEdit={relationshipsData?.properties}
          schema={parentSchema}
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
                      <Icon icon={"mdi:layers-triple"} />
                      <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
                    </div>
                  </div>
                  <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20 mr-2">
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
            objectname={relatedObjectToEdit.__typename}
          />
        </SlideOver>
      )}
    </Fragment>
  );
}
