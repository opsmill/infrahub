import { MenuItem, MenuSection } from "@infrahub/ui";
import { ArrowUpRightIcon, PlayIcon } from "lucide-react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { canRunGenerators } from "@/entities/generators/domain/rules/can-run-generators";
import { useGetNodeGeneratorDefinitions } from "@/entities/generators/ui/queries/get-node-generator-definitions.query";
import { useRunGeneratorMutation } from "@/entities/generators/ui/queries/run-generator.mutation";
import { EDIT_DEFAULT_BRANCH } from "@/entities/permission/domain/model/permission";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";
import { getTaskDetailsUrl } from "@/entities/tasks/ui/routing/task-urls";

export interface NodeGeneratorsMenuSectionProps {
  nodeId: string;
  nodeKind: string;
  nodeLabel: string;
}

export function NodeGeneratorsMenuSection({
  nodeId,
  nodeKind,
  nodeLabel,
}: NodeGeneratorsMenuSectionProps) {
  const { isAuthenticated } = useAuth();
  const { currentBranch } = useCurrentBranch();
  const isDefaultBranch = !!currentBranch.is_default;
  const { data: hasEditDefaultBranch } = useHasGlobalPermission(EDIT_DEFAULT_BRANCH, {
    enabled: isAuthenticated && isDefaultBranch,
  });
  const canRun = canRunGenerators({ isAuthenticated, isDefaultBranch, hasEditDefaultBranch });

  const { data: definitions } = useGetNodeGeneratorDefinitions(
    { nodeId, nodeKind },
    { enabled: canRun }
  );

  const getGeneratorLabel = (generatorId: string) =>
    definitions?.find(({ id }) => id === generatorId)?.label ?? generatorId;

  // Callbacks are hook options, not `mutate` options, because selecting an item closes the menu
  // and unmounts this section before the request returns.
  const { mutate, isPending, variables } = useRunGeneratorMutation({
    onSuccess: ({ taskId }, { generatorId }) => {
      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={
            <>
              <span>
                Generator {getGeneratorLabel(generatorId)} started for {nodeLabel}.
              </span>
              <br />
              <Link
                to={getTaskDetailsUrl(taskId)}
                className="inline-flex items-center gap-1 underline"
              >
                View task <ArrowUpRightIcon className="size-3.5" />
              </Link>
            </>
          }
        />
      );
    },
    onError: (error, { generatorId }) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Could not start generator ${getGeneratorLabel(generatorId)}: ${error.message}`}
        />
      );
    },
  });

  if (!canRun || !definitions?.length) return null;

  return (
    <MenuSection title="Generators">
      {definitions.map((definition) => (
        <MenuItem
          key={definition.id}
          textValue={`Run ${definition.label}`}
          isDisabled={
            !definition.isMember || (isPending && variables?.generatorId === definition.id)
          }
          tooltip={
            definition.isMember
              ? undefined
              : `${nodeLabel} is not a member of the target group ${definition.groupLabel}`
          }
          onAction={() =>
            mutate({
              generatorId: definition.id,
              targetNodeIds: [nodeId],
              processErrorMessage: () => {},
            })
          }
        >
          <PlayIcon />
          <span>Run {definition.label}</span>
        </MenuItem>
      ))}
    </MenuSection>
  );
}
