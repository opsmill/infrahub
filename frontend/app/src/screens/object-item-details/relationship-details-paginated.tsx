import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/components/display/meta-details-tooltips";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ModalDelete from "@/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Link as StyledLink } from "@/components/ui/link";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import useQuery from "@/hooks/useQuery";
import NoDataFound from "@/screens/errors/no-data-found";
import ObjectItemEditComponent from "@/screens/object-item-edit/object-item-edit-paginated";
import { ObjectItemsCell, TextCell } from "@/screens/object-items/object-items-cell";
import { getPermission } from "@/screens/permission/utils";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { showMetaEditState } from "@/state/atoms/metaEditFieldDetails.atom";
import { schemaState } from "@/state/atoms/schema.atom";
import { metaEditFieldDetailsState } from "@/state/atoms/showMetaEdit.atom copy";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { constructPath } from "@/utils/fetch";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { getObjectDetailsUrl } from "@/utils/objects";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { EyeSlashIcon, LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import ErrorScreen from "../errors/error-screen";
import UnauthorizedScreen from "../errors/unauthorized-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import { getObjectPermissionsQuery } from "../permission/queries/getObjectPermissions";
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

  const { objectKind, objectid } = useParams();

  const schemaList = useAtomValue(schemaState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const [relatedRowToDelete, setRelatedRowToDelete] = useState<any>();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState<any>();

  const parentSchema = schemaList.find((s) => s.kind === objectKind);
  const columns = getSchemaObjectColumns({
    schema: relationshipSchemaData,
    forListView: mode === "TABLE",
  }).filter((column) => {
    if (column.isAttribute) return true;

    return relationshipsData?.some((relationship: { node: any }) => {
      const relatedObject = relationship.node[column.name]?.node;
      if (!relatedObject) return true;

      return relatedObject.id !== objectid;
    });
  });

  const [, setShowMetaEditModal] = useAtom(showMetaEditState);
  const [, setMetaEditFieldDetails] = useAtom(metaEditFieldDetailsState);

  const { loading, data, error } = useQuery(gql(getObjectPermissionsQuery(objectKind)));

  const permission = data && getPermission(data?.[objectKind]?.permissions?.edges);

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="Something went wrong when fetching IPAM details." />;
  }

  if (loading) {
    return <LoadingScreen />;
  }

  if (relationshipsData && relationshipsData?.properties?.is_visible === false) {
    return null;
  }

  if (relationshipSchema?.cardinality === "many" && !Array.isArray(relationshipsData)) {
    return null;
  }

  const handleDeleteRelationship = async (id: string) => {
    if (onDeleteRelationship) {
      await onDeleteRelationship(relationshipSchema.name, id);

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
                      )}
                    >
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
                              disabled={!permission?.create.isAllowed}
                              tooltipEnabled={!permission?.create.isAllowed}
                              tooltipContent={permission?.create.message ?? undefined}
                              onClick={() => {
                                setMetaEditFieldDetails({
                                  type: "relationship",
                                  attributeOrRelationshipName: relationshipSchema.name,
                                  label: relationshipSchema.label || relationshipSchema.name,
                                });
                                setShowMetaEditModal(true);
                              }}
                              data-cy="metadata-edit-button"
                            >
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
                      <th key={column.name} scope="col" className="h-9 font-semibold">
                        <TextCell>{column.label}</TextCell>
                      </th>
                    ))}

                    <th scope="col"></th>
                  </tr>
                </thead>

                <tbody className="bg-custom-white">
                  {relationshipsData?.map(({ node, properties }: any, index: number) => (
                    <tr
                      key={index}
                      className="border-b border-gray-200 hover:bg-gray-50"
                      data-testid="relationship-row"
                    >
                      {newColumns?.map((column) => (
                        <td key={node.id + column.name} className="h-9">
                          <ObjectItemsCell row={node} attribute={column} />
                        </td>
                      ))}

                      <td className="h-9 text-right">
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
                          disabled={!permission.update.isAllowed}
                          tooltipEnabled={!permission.update.isAllowed}
                          tooltipContent={permission.update.message ?? undefined}
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setRelatedObjectToEdit(node);
                          }}
                          data-cy="metadata-edit-button"
                        >
                          <Icon icon="mdi:pencil" className="text-custom-blue-500" />
                        </ButtonWithTooltip>

                        <ButtonWithTooltip
                          disabled={!permission.update.isAllowed}
                          tooltipEnabled={!permission.update.isAllowed}
                          tooltipContent={permission.update.message ?? undefined}
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setRelatedRowToDelete(node);
                          }}
                          data-testid="relationship-delete-button"
                        >
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
          confirmLabel="Remove"
        />
      )}

      {relatedObjectToEdit && (
        <SlideOver
          title={
            parentSchema && (
              <SlideOverTitle
                schema={parentSchema}
                currentObjectLabel={relationshipSchema.label}
                title={`Edit ${relatedObjectToEdit?.display_label}`}
                subtitle="Update the details of the related object"
              />
            )
          }
          open={!!relatedObjectToEdit}
          setOpen={() => setRelatedObjectToEdit(undefined)}
        >
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
