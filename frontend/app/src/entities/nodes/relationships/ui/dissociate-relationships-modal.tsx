import { toast } from "react-toastify";

import { ModalDelete } from "@/shared/components/aria/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useRemoveRelationships } from "@/entities/nodes/relationships/domain/remove-relationships/remove-relationships.mutation";

export interface DissociateRelationshipModalProps {
  objectId: string;
  relationshipIds: string[];
  relationshipLabel: string;
  relationshipName: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DissociateRelationshipsModal({
  objectId,
  relationshipLabel,
  relationshipName,
  relationshipIds,
  isOpen,
  onOpenChange,
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
          toast(
            <Alert
              type={ALERT_TYPES.SUCCESS}
              message={`Association with ${relationshipLabel} removed`}
            />
          );
          onOpenChange(false);
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
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      onDelete={handleRemoveRelationships}
      isLoading={isPending}
    />
  );
}
