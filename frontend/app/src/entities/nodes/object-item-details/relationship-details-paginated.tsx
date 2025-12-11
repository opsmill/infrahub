import { gql } from "@apollo/client";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai";
import { Fragment, useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import MetaDetailsTooltip from "@/shared/components/display/meta-details-tooltips";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link as StyledLink } from "@/shared/components/ui/link";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { currentBranchAtom } from "@/entities/branches/stores";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import ObjectItemEditComponent from "@/entities/nodes/object-item-edit/object-item-edit-paginated";
import { getSchemaObjectColumns } from "@/entities/nodes/object-items/getSchemaObjectColumns";
import { ObjectItemsCell, TextCell } from "@/entities/nodes/object-items/object-items-cell";
import { showMetaEditState } from "@/entities/nodes/stores/metaEditFieldDetails.atom";
import { metaEditFieldDetailsState } from "@/entities/nodes/stores/showMetaEdit.atom";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { getPermission } from "@/entities/permission/utils";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { getObjectPermissionsQuery } from "../../permission/queries/getObjectPermissions";
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

  const { objectKind, objectId } = useParams();

  const schemaList = useAtomValue(nodeSchemasAtom);
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

      return relatedObject.id !== objectId;
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
    return <LoadingIndicator className="h-12" />;
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
        id: objectId,
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
                      to={getObjectDetailsUrl(
                        relationshipsData.node?.__typename,
                        relationshipsData.node?.id
                      )}
                    >
                      {relationshipsData.node ? getNodeLabel(relationshipsData.node) : "-"}
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
                          <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
                            <div className="font-semibold">{relationshipSchema.label}</div>

                            <ButtonWithTooltip
                              variant="ghost"
                              size="icon"
                              disabled={!permission?.update.isAllowed}
                              tooltipEnabled={!permission?.update.isAllowed}
                              tooltipContent={permission?.update.message ?? undefined}
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
                    <LockClosedIcon className="h-4 w-4" />
                  )}
                </>
              }
            />
          )}

          {relationshipSchema?.cardinality === "many" && mode === "TABLE" && (
            <div className="flex-1 overflow-x-auto shadow-xs ring-1 ring-custom-black ring-opacity-5">
              <table className="w-full table-auto border-spacing-0" cellPadding="0">
                <thead className="border-gray-300 border-b bg-gray-50 text-left">
                  <tr>
                    {newColumns?.map((column) => (
                      <th key={column.name} scope="col" className="h-9 font-semibold">
                        <TextCell>{column.label}</TextCell>
                      </th>
                    ))}

                    <th scope="col"></th>
                  </tr>
                </thead>

                <tbody className="bg-white">
                  {relationshipsData?.map(({ node, properties }: any, index: number) => (
                    <tr
                      key={index}
                      className="border-gray-200 border-b hover:bg-gray-50"
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
                              <div className="flex items-center justify-between border-gray-200 border-b p-1 pt-0 pl-2">
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
                    <dd className="flex items-center text-gray-900 underline" key={node.id}>
                      <Link to={getObjectDetailsUrl(node.__typename, node.id)}>
                        {getNodeLabel(node)}
                      </Link>

                      {node && (
                        <div className="p-2">
                          <MetaDetailsTooltip
                            updatedAt={properties.updated_at}
                            source={properties.source}
                            owner={properties.owner}
                            isProtected={properties.is_protected}
                          />
                        </div>
                      )}

                      {properties.is_protected && <LockClosedIcon className="h-4 w-4" />}
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
              <b>`{getNodeLabel(props.parentNode)}`</b> and{" "}
              <b>`{getNodeLabel(relatedRowToDelete)}`</b>? The{" "}
              <b>`{relatedRowToDelete.__typename.replace(regex, "")}`</b>{" "}
              <b>`{getNodeLabel(relatedRowToDelete)}`</b> won&apos;t be deleted in the process.
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
                title={`Edit ${relatedObjectToEdit ? getNodeLabel(relatedObjectToEdit) : ""}`}
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
            objectId={relatedObjectToEdit.id}
            objectname={relatedObjectToEdit.__typename}
          />
        </SlideOver>
      )}
    </Fragment>
  );
}
