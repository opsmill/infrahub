import { gql } from "@apollo/client";
import { PencilSquareIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";
import { BUTTON_TYPES, Button } from "../../components/buttons/button";
import SlideOver from "../../components/display/slide-over";
import ModalDelete from "../../components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { DEFAULT_BRANCH_NAME } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
// import { ReactComponent as UnlinkIcon } from "../../images/icons/unlink.svg";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { removeRelationship } from "../../graphql/mutations/relationships/removeRelationship";
import UnlinkIcon from "../../images/icons/unlink.svg";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { iNodeSchema, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { classNames } from "../../utils/common";
import { getObjectItemDisplayValue } from "../../utils/getObjectItemDisplayValue";
import { getObjectDetailsUrl } from "../../utils/objects";
import { stringifyWithoutQuotes } from "../../utils/string";
import NoDataFound from "../no-data-found/no-data-found";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import { useAuth } from "../../decorators/auth";

type iRelationDetailsProps = {
  parentNode: any;
  parentSchema: iNodeSchema;
  relationshipsData: any;
  relationshipSchema: any;
  refetch?: Function;
  onDeleteRelationship?: Function;
};

const regex = /^Related/; // starts with Related

export default function RelationshipDetails(props: iRelationDetailsProps) {
  const { relationshipsData, relationshipSchema, refetch } = props;

  const { groupid } = useParams();
  const auth = useAuth();

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<any>();
  const [relatedObjectToEdit, setRelatedObjectToEdit] = useState<any>();

  const navigate = useNavigate();

  if (relationshipsData && relationshipsData?.properties?.is_visible === false) {
    return null;
  }

  if (relationshipSchema?.cardinality === "many" && !Array.isArray(relationshipsData)) {
    return null;
  }

  const handleDeleteRelationship = async (id: string) => {
    const mutationString = removeRelationship({
      data: stringifyWithoutQuotes({
        id: groupid,
        name: "members",
        nodes: [
          {
            id,
          },
        ],
      }),
    });

    const mutation = gql`
      ${mutationString}
    `;

    await graphqlClient.mutate({
      mutation,
      context: { branch: branch?.name, date },
    });

    setRelatedRowToDelete(null);

    if (refetch) {
      refetch();
    }

    toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Item removed from the group"} />);
  };

  // TODO: Refactor reltionships components to compute the correct columns
  const columns = [
    { label: "Type", name: "__typename" },
    { label: "Name", name: "display_label" },
  ];

  return (
    <>
      <div key={relationshipSchema?.name}>
        {!relationshipsData && (
          <div className="py-4 sm:grid sm:grid-cols-3 sm:gap-4 sm:py-4 sm:px-6">
            <dt className="text-sm font-medium text-gray-500 flex items-center">
              {relationshipSchema?.label}
            </dt>
            <dd className="text-sm text-gray-900  flex items-center">-</dd>
          </div>
        )}

        {relationshipsData && (
          <div className="flex-1 shadow-sm ring-1 ring-custom-black ring-opacity-5 overflow-x-auto">
            <table className="min-w-full border-separate" style={{ borderSpacing: 0 }}>
              <thead className="bg-gray-50">
                <tr>
                  {columns?.map((column) => (
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
                {relationshipsData?.map(({ node }: any, index: number) => (
                  <tr
                    onClick={() => navigate(getObjectDetailsUrl(node.id, node.__typename))}
                    key={index}
                    className="hover:bg-gray-50 cursor-pointer">
                    {columns?.map((column) => (
                      <td
                        key={node.id + "-" + column.name}
                        className={classNames(
                          index !== relationshipsData.length - 1 ? "border-b border-gray-200" : "",
                          "whitespace-nowrap p-4 text-sm font-medium text-gray-900"
                        )}>
                        {getObjectItemDisplayValue(node, column, schemaKindName)}
                      </td>
                    ))}
                    <td
                      className={classNames(
                        index !== relationshipsData.length - 1 ? "border-b border-gray-200" : "",
                        "whitespace-nowrap p-4 text-sm font-medium text-gray-900"
                      )}>
                      <Button
                        disabled={!auth?.permissions?.write}
                        buttonType={BUTTON_TYPES.INVISIBLE}
                        onClick={() => {
                          setRelatedObjectToEdit(node);
                        }}>
                        <PencilSquareIcon className="w-4 h-4 text-gray-500" />
                      </Button>

                      <Button
                        disabled={!auth?.permissions?.write}
                        buttonType={BUTTON_TYPES.INVISIBLE}
                        onClick={() => {
                          setRelatedRowToDelete(node);
                        }}>
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
