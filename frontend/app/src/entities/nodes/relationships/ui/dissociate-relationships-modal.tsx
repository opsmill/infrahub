import { useRemoveRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships.mutation";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { toast } from "react-toastify";

export interface DissociateRelationshipModalProps {
  objectId: string;
  relationshipIds: string[];
  relationshipLabel: string;
  relationshipName: string;
  open: boolean;
  setOpen: (b: boolean) => void;
}

export function DissociateRelationshipsModal({
  objectId,
  relationshipLabel,
  relationshipName,
  relationshipIds,
  open,
  setOpen,
}: DissociateRelationshipModalProps) {
  const { mutate, isPending } = useRemoveRelationships();

  const handleRemoveRelationships = () => {
    mutate(
      {
        objectId,
        relationshipName,
        relationshipIds,
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes("objects"),
          });
          graphqlClient.reFetchObservableQueries();
          setOpen(false);
          toast(
            <Alert
              type={ALERT_TYPES.SUCCESS}
              message={`Association with ${relationshipLabel} removed`}
            />
          );
        },
      }
    );
  };

  return (
    <ModalDelete
      title="Dissociate"
      description={
        <>
          <p className="mb-2">
            Are you sure you want to dissociate <strong>{relationshipLabel}</strong> ?
          </p>

          <ul>
            <li>- This action will only remove the association.</li>
            <li>- The object itself will not be deleted.</li>
          </ul>
        </>
      }
      open={open}
      setOpen={setOpen}
      onCancel={() => setOpen(false)}
      onDelete={handleRemoveRelationships}
      isLoading={isPending}
    />
  );
}
