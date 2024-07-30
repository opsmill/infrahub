import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { RoundedButton } from "@/components/buttons/rounded-button";
import MetaDetailsTooltip from "@/components/display/meta-details-tooltips";
import SlideOver from "@/components/display/slide-over";
import { SelectOption } from "@/components/inputs/select";
import ModalDelete from "@/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Link as StyledLink } from "@/components/ui/link";
import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { ADD_RELATIONSHIP } from "@/graphql/mutations/relationships/addRelationship";
import { usePermission } from "@/hooks/usePermission";
import NoDataFound from "@/screens/errors/no-data-found";
import ObjectItemEditComponent from "@/screens/object-item-edit/object-item-edit-paginated";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { showMetaEditState } from "@/state/atoms/metaEditFieldDetails.atom";
import { genericsState, schemaState } from "@/state/atoms/schema.atom";
import { metaEditFieldDetailsState } from "@/state/atoms/showMetaEdit.atom copy";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { constructPath } from "@/utils/fetch";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/utils/objects";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useMutation } from "@/hooks/useQuery";
import { EyeSlashIcon, LockClosedIcon, PlusIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { ObjectAttributeRow } from "./object-attribute-row";
import DynamicForm from "@/components/form/dynamic-form";
import ObjectItemsCell from "@/screens/object-items/object-items-cell";

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

  const { objectKind, objectid } = useParams();
  const permission = usePermission();

  const schemaList = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [addRelationship] = useMutation(ADD_RELATIONSHIP);

  const [showAddDrawer, setShowAddDrawer] = useState(false);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<any>();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState<any>();

  const parentSchema = schemaList.find((s) => s.kind === objectKind);
  const generic = generics.find((g) => g.kind === relationshipSchemaData?.kind);
  const columns = getSchemaObjectColumns({
    schema: relationshipSchemaData,
    forListView: mode === "TABLE",
  });

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
    const { relation } = data;

    if (relation?.id || relation?.from_pool) {
      await addRelationship({
        variables: {
          objectId: objectid,
          relationshipIds: [relation],
          relationshipName: relationshipSchema.name,
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
                  {relationshipsData.node?.id ? (
                    <StyledLink
                      to={constructPath(
                        getObjectDetailsUrl(
                          relationshipsData.node?.id,
                          relationshipsData.node?.__typename
                        )
                      )}>
                      {relationshipsData.node?.display_label}
                    </StyledLink>
                  ) : (
                    "-"
                  )}

                  {relationshipsData.properties && (
                    <div className="px-2">
                      <MetaDetailsTooltip
                        updatedAt={relationshipsData.properties.updated_at}
                        source={relationshipsData.properties.source}
                        owner={relationshipsData.properties.owner}
                        isProtected={relationshipsData.properties.is_protected}
                        header={
                          <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b">
                            <div className="font-semibold">{relationshipSchema.label}</div>

                            <ButtonWithTooltip
                              variant="ghost"
                              size="icon"
                              disabled={!permission.write.allow}
                              tooltipEnabled={!permission.write.allow}
                              tooltipContent={permission.write.message ?? undefined}
                              onClick={() => {
                                setMetaEditFieldDetails({
                                  type: "relationship",
                                  attributeOrRelationshipName: relationshipSchema.name,
                                  label: relationshipSchema.label || relationshipSchema.name,
                                });
                                setShowMetaEditModal(true);
                              }}
                              data-cy="metadata-edit-button">
                              <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                            </ButtonWithTooltip>
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
              <table className="table-auto border-spacing-0 w-full" cellPadding="0">
                <thead className="bg-gray-50 text-left border-b border-gray-300">
                  <tr>
                    {newColumns?.map((column) => (
                      <th
                        key={column.name}
                        scope="col"
                        className="px-2 py-3 text-xs font-semibold text-gray-900">
                        {column.label}
                      </th>
                    ))}

                    <th scope="col"></th>
                  </tr>
                </thead>

                <tbody className="bg-custom-white">
                  {relationshipsData?.map(({ node, properties }: any, index: number) => (
                    <tr
                      key={index}
                      className="border-b border-gray-200 h-[36px] hover:bg-gray-50"
                      data-cy="relationship-row"
                      data-testid="relationship-row">
                      {newColumns?.map((column) => (
                        <ObjectItemsCell
                          key={node.id + column.name}
                          row={node}
                          attribute={column}
                        />
                      ))}

                      <td className="text-right">
                        {properties && (
                          <MetaDetailsTooltip
                            updatedAt={properties.updated_at}
                            source={properties.source}
                            owner={properties.owner}
                            isProtected={properties.is_protected}
                            header={
                              <div className="flex justify-between items-center pl-2 p-1 pt-0 border-b">
                                <div className="font-semibold">{relationshipSchema.label}</div>
                              </div>
                            }
                          />
                        )}

                        <ButtonWithTooltip
                          disabled={!permission.write.allow}
                          tooltipEnabled={!permission.write.allow}
                          tooltipContent={permission.write.message ?? undefined}
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setRelatedObjectToEdit(node);
                          }}
                          data-cy="metadata-edit-button">
                          <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                        </ButtonWithTooltip>

                        <ButtonWithTooltip
                          disabled={!permission.write.allow}
                          tooltipEnabled={!permission.write.allow}
                          tooltipContent={permission.write.message ?? undefined}
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setRelatedRowToDelete(node);
                          }}
                          data-testid="relationship-delete-button">
                          <Icon icon="mdi:link-variant-remove" className="text-base text-red-600" />
                        </ButtonWithTooltip>
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
                            updatedAt={properties.updated_at}
                            source={properties._relation__source}
                            owner={properties.owner}
                            isProtected={properties.is_protected}
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
            disabled={!permission.write.allow}
            onClick={() => setShowAddDrawer(true)}
            className="p-3 ml-2 bg-custom-blue-500 hover:bg-custom-blue-500 focus:ring-custom-blue-500 focus:ring-offset-gray-50 focus:ring-offset-2"
            data-testid="open-relationship-form-button">
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
        <DynamicForm
          fields={[
            {
              name: "relation",
              label: relationshipSchema.label,
              type: "relationship",
              relationship: { ...relationshipSchema, cardinality: "one", inherited: true },
              schema: relationshipSchemaData,
              options,
            },
          ]}
          onSubmit={async ({ relation }) => {
            await handleSubmit({ relation: relation.value });
          }}
          onCancel={() => {
            setShowAddDrawer(false);
          }}
          className="w-full p-4"
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
