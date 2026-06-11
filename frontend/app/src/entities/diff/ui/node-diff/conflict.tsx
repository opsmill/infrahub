import { Icon } from "@iconify-icon/react";
import { Checkbox, Spinner } from "@infrahub/ui";
import { toast } from "react-toastify";

import type { ConflictSelection } from "@/shared/api/graphql/generated/types";
import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { treeQueryKeys } from "@/entities/diff/ui/queries/diff.query-keys";
import { useResolveConflictMutation } from "@/entities/diff/ui/queries/resolve-conflict.mutation";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

interface ConflictData {
  id: string;
  selectedBranch?: ConflictSelection | null;
}

export const Conflict = ({ id, selectedBranch }: ConflictData) => {
  const proposedChange = useProposedChange();
  const { mutate, isPending } = useResolveConflictMutation();

  const { isAuthenticated } = useAuth();

  const handleAccept = (conflictValue: ConflictSelection) => {
    const newValue = conflictValue === selectedBranch ? null : conflictValue;

    mutate(
      {
        id,
        selection: newValue,
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({ queryKey: treeQueryKeys.all });
          await queryClient.invalidateQueries({ queryKey: [...tasksQueryKeys.all, "check"] });

          const message = newValue
            ? "Conflict marked as resolved"
            : "Conflict marked as not resolved";

          toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
        },
        onError: ({ message }) => {
          toast(<Alert type={ALERT_TYPES.ERROR} message={message} />);
        },
      }
    );
  };

  return (
    <Row className="justify-end p-2">
      {isPending && <Spinner />}

      <span className="text-xs">Choose the branch to resolve the conflict:</span>

      <Checkbox
        isDisabled={isPending || !isAuthenticated}
        isSelected={selectedBranch === "BASE_BRANCH"}
        onChange={() => handleAccept("BASE_BRANCH")}
      >
        <Badge variant="green">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {proposedChange.destination_branch?.value ?? "Base Branch"}
        </Badge>
      </Checkbox>

      <Checkbox
        isDisabled={isPending || !isAuthenticated}
        isSelected={selectedBranch === "DIFF_BRANCH"}
        onChange={() => handleAccept("DIFF_BRANCH")}
      >
        <Badge variant="blue">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {proposedChange.source_branch?.value ?? "Diff Branch"}
        </Badge>
      </Checkbox>
    </Row>
  );
};
