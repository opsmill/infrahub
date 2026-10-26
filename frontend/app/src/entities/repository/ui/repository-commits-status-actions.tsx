import { Button, Tooltip } from "@infrahub/ui";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLineIcon,
  GitBranchIcon,
  type LucideIcon,
  RadarIcon,
  RefreshCwIcon,
} from "lucide-react";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import {
  type RepositoryCommitLog,
  RepositoryGitCondition,
} from "@/entities/repository/domain/model/repository";
import type { RepositoryCommitsActions } from "@/entities/repository/ui/hooks/use-repository-commits-actions";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  type CommitLogAction,
  type CommitLogActionKind,
  getDeniedReason,
  getDeniedReasons,
  type RepositoryCommitsRepository,
} from "@/entities/repository/ui/repository-commits.view";

const ACTION_LABEL: Record<CommitLogActionKind, string> = {
  import: "Import latest commit",
  rebase: "Rebase branch",
  check: "Check remote now",
  refresh: "Refresh",
};

const ACTION_ICON: Record<CommitLogActionKind, LucideIcon> = {
  import: ArrowDownToLineIcon,
  rebase: GitBranchIcon,
  check: RadarIcon,
  refresh: RefreshCwIcon,
};

export interface RepositoryCommitsStatusActionsProps {
  primary: CommitLogAction | null;
  secondary: CommitLogAction | null;
  condition: RepositoryCommitLog["condition"] | null;
  repository: RepositoryCommitsRepository;
  actions: RepositoryCommitsActions;
}

export function RepositoryCommitsStatusActions({
  primary,
  secondary,
  condition,
  repository,
  actions,
}: RepositoryCommitsStatusActionsProps) {
  const queryClient = useQueryClient();
  const { currentBranch } = useCurrentBranch();
  const [isConfirmingRebase, setIsConfirmingRebase] = React.useState(false);
  const reasonIdPrefix = React.useId();
  const commitLogKey = repositoriesQueryKeys.repository({
    repositoryId: repository.id,
    branchName: currentBranch.name,
  });
  const deniedReasons = getDeniedReasons([secondary, primary]);
  const getReasonId = (action: CommitLogAction) => {
    const reason = getDeniedReason(action);
    return reason ? `${reasonIdPrefix}-${deniedReasons.indexOf(reason)}` : undefined;
  };

  const onPress = ({ kind }: CommitLogAction) => {
    switch (kind) {
      case "import":
        return actions.importLatestCommit();
      case "rebase":
        return setIsConfirmingRebase(true);
      case "check":
        return actions.checkRemote();
      case "refresh":
        return queryClient.invalidateQueries({ queryKey: commitLogKey });
    }
  };

  return (
    <>
      <Col className="shrink-0 items-start gap-1.5">
        {(secondary || primary) && (
          <Row className="flex-wrap gap-2">
            {secondary && (
              <CommitLogActionButton
                action={secondary}
                actions={actions}
                commitLogKey={commitLogKey}
                describedBy={getReasonId(secondary)}
                onPress={() => onPress(secondary)}
              />
            )}
            {primary && (
              <CommitLogActionButton
                action={primary}
                actions={actions}
                commitLogKey={commitLogKey}
                describedBy={getReasonId(primary)}
                onPress={() => onPress(primary)}
                isPrimary
              />
            )}
          </Row>
        )}
        {deniedReasons.map((reason, index) => (
          <p
            key={reason}
            id={`${reasonIdPrefix}-${index}`}
            className="max-w-72 text-foreground-muted text-xs"
          >
            {reason}
          </p>
        ))}
      </Col>
      <RebaseConfirm
        condition={condition}
        repositoryName={repository.name}
        isOpen={isConfirmingRebase}
        onOpenChange={setIsConfirmingRebase}
        isLoading={actions.submitting === "rebase"}
        onConfirm={() => actions.rebaseBranch({ onSettled: () => setIsConfirmingRebase(false) })}
      />
    </>
  );
}

interface CommitLogActionButtonProps {
  action: CommitLogAction;
  actions: Pick<RepositoryCommitsActions, "submitting" | "isCheckRunning">;
  commitLogKey: readonly unknown[];
  describedBy?: string;
  onPress: () => void;
  isPrimary?: boolean;
}

export function CommitLogActionButton({
  action,
  actions,
  commitLogKey,
  describedBy,
  onPress,
  isPrimary = false,
}: CommitLogActionButtonProps) {
  const isRefreshing = useIsFetching({ queryKey: commitLogKey }) > 0;
  const Icon = ACTION_ICON[action.kind];
  const isCheckRunning = action.kind === "check" && actions.isCheckRunning;
  const deniedReason = getDeniedReason(action);
  const isSubmitting = actions.submitting === action.kind;

  return (
    <Tooltip message={deniedReason ?? undefined}>
      <Button
        variant={isPrimary ? "primary" : "outline"}
        size="sm"
        isDisabled={
          !deniedReason && (action.access.status === "pending" || isCheckRunning || isSubmitting)
        }
        isDisabledAndFocusable={!!deniedReason}
        isPending={isSubmitting || (action.kind === "refresh" && isRefreshing)}
        aria-describedby={describedBy}
        onPress={onPress}
      >
        <Icon aria-hidden="true" />
        {isCheckRunning ? "Check running" : ACTION_LABEL[action.kind]}
      </Button>
    </Tooltip>
  );
}

const CONDITIONS_WITHOUT_CURRENT_COMMIT: RepositoryGitCondition[] = [
  RepositoryGitCondition.REWRITTEN,
  RepositoryGitCondition.ORPHANED,
];

interface RebaseConfirmProps {
  condition: RepositoryCommitLog["condition"] | null;
  repositoryName: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  isLoading: boolean;
  onConfirm: () => void;
}

function RebaseConfirm({
  condition,
  repositoryName,
  isOpen,
  onOpenChange,
  isLoading,
  onConfirm,
}: RebaseConfirmProps) {
  const branchName = useCurrentBranch().currentBranch.name;
  const defaultBranchName = useDefaultBranch()?.name ?? null;
  const mayKeepOwnCommit =
    condition !== null && CONDITIONS_WITHOUT_CURRENT_COMMIT.includes(condition);

  return (
    <ModalConfirm
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title="Rebase the whole branch?"
      confirmLabel="Rebase branch"
      isLoading={isLoading}
      onConfirm={onConfirm}
      description={
        <>
          <span className="break-all font-semibold text-foreground">{branchName}</span> is rebased
          on {defaultBranchName ? <Ref>{defaultBranchName}</Ref> : "the default branch"}. Every
          change on this branch is rebased: all its data and all its repositories, not only{" "}
          {repositoryName}.
          {mayKeepOwnCommit &&
            ` If the branch has a commit of its own in ${repositoryName}, the rebase does not replace it.`}
        </>
      }
    />
  );
}

export function Ref({ children }: { children: string }) {
  return (
    <code title={children} className="inline-block max-w-64 truncate align-bottom font-mono">
      {children}
    </code>
  );
}
