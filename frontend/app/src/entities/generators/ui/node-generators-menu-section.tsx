import { MenuItem, MenuSection } from "@infrahub/ui";
import { ArrowUpRightIcon, PlayIcon } from "lucide-react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { NodeGeneratorDefinition } from "@/entities/generators/domain/model/node-generator-definition";
import { canRunGenerators } from "@/entities/generators/domain/rules/can-run-generators";
import { useGetNodeGeneratorDefinitions } from "@/entities/generators/ui/queries/get-node-generator-definitions.query";
import { useRunGeneratorMutation } from "@/entities/generators/ui/queries/run-generator.mutation";
import type { NodeCore } from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { EDIT_DEFAULT_BRANCH } from "@/entities/permission/domain/model/permission";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";
import { getTaskDetailsUrl } from "@/entities/tasks/ui/routing/task-urls";

export interface NodeGeneratorsMenuSectionProps {
  node: NodeCore;
}

export function NodeGeneratorsMenuSection({ node }: NodeGeneratorsMenuSectionProps) {
  const canRun = useCanRunGenerators();
  const { data: definitions = [] } = useGetNodeGeneratorDefinitions(
    { nodeId: node.id, nodeKind: node.__typename },
    { enabled: canRun }
  );

  if (!canRun || definitions.length === 0) return null;

  return (
    <MenuSection title="Generators">
      {definitions.map((definition) => (
        <RunGeneratorMenuItem key={definition.id} definition={definition} node={node} />
      ))}
    </MenuSection>
  );
}

function useCanRunGenerators() {
  const { isAuthenticated } = useAuth();
  const { currentBranch } = useCurrentBranch();
  const isDefaultBranch = !!currentBranch.is_default;
  const { data: hasEditDefaultBranch } = useHasGlobalPermission(EDIT_DEFAULT_BRANCH, {
    enabled: isAuthenticated && isDefaultBranch,
  });

  return canRunGenerators({ isAuthenticated, isDefaultBranch, hasEditDefaultBranch });
}

interface RunGeneratorMenuItemProps {
  definition: NodeGeneratorDefinition;
  node: NodeCore;
}

function RunGeneratorMenuItem({ definition, node }: RunGeneratorMenuItemProps) {
  const nodeLabel = getNodeLabel(node);

  // Callbacks are hook options, not `mutate` options, because selecting the item closes the menu
  // and unmounts it before the request returns.
  const { mutate, isPending } = useRunGeneratorMutation({
    onSuccess: ({ taskId }) => {
      toast(
        <GeneratorStartedAlert
          generatorLabel={definition.label}
          nodeLabel={nodeLabel}
          taskId={taskId}
        />
      );
    },
    onError: (error) => {
      toast(<GeneratorNotStartedAlert generatorLabel={definition.label} reason={error.message} />);
    },
  });

  const notMemberMessage = definition.isMember
    ? undefined
    : `${nodeLabel} is not a member of the target group ${definition.groupLabel}`;

  return (
    <MenuItem
      id={definition.id}
      textValue={`Run ${definition.label}`}
      isDisabled={!definition.isMember || isPending}
      tooltip={notMemberMessage}
      onAction={() =>
        mutate({
          generatorId: definition.id,
          targetNodeIds: [node.id],
          processErrorMessage: () => {},
        })
      }
    >
      <PlayIcon />
      <span>Run {definition.label}</span>
    </MenuItem>
  );
}

interface GeneratorStartedAlertProps {
  generatorLabel: string;
  nodeLabel: string;
  taskId: string;
}

function GeneratorStartedAlert({ generatorLabel, nodeLabel, taskId }: GeneratorStartedAlertProps) {
  return (
    <Alert
      type={ALERT_TYPES.SUCCESS}
      message={
        <>
          <span>
            Generator {generatorLabel} started for {nodeLabel}.
          </span>
          <br />
          <Link to={getTaskDetailsUrl(taskId)} className="inline-flex items-center gap-1 underline">
            View task <ArrowUpRightIcon className="size-3.5" />
          </Link>
        </>
      }
    />
  );
}

interface GeneratorNotStartedAlertProps {
  generatorLabel: string;
  reason: string;
}

function GeneratorNotStartedAlert({ generatorLabel, reason }: GeneratorNotStartedAlertProps) {
  return (
    <Alert
      type={ALERT_TYPES.ERROR}
      message={`Could not start generator ${generatorLabel}: ${reason}`}
    />
  );
}
