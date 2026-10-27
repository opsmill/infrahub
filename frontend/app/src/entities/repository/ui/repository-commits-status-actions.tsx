import { Button, Tooltip } from "@infrahub/ui";
import { ArrowDownToLineIcon, GitBranchIcon, type LucideIcon, RadarIcon } from "lucide-react";
import React from "react";

import { RefreshButton } from "@/shared/components/buttons/refresh-button";
import { Col, Row } from "@/shared/components/container";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import type { RepositoryCommitLog } from "@/entities/repository/domain/model/repository";
import type { RepositoryCommitsActions } from "@/entities/repository/ui/hooks/use-repository-commits-actions";
import { repositoriesQueryKeys } from "@/entities/repository/ui/queries/repository.query-keys";
import {
  type CommitLogAction,
  type CommitLogActionKind,
  getDeniedReason,
  mayKeepOwnCommit,
  type RepositoryCommitsRepository,
} from "@/entities/repository/ui/repository-commits.view";

const ACTION_LABEL: Record<CommitLogActionKind, string> = {
  import: "Import latest commit",
  rebase: "Rebase branch",
  check: "Check remote now",
};

const ACTION_ICON: Record<CommitLogActionKind, LucideIcon> = {
  import: ArrowDownToLineIcon,
  rebase: GitBranchIcon,
  check: RadarIcon,
};

export interface RepositoryCommitsStatusActionsProps {
  primary: CommitLogAction | null;
  secondary: CommitLogAction | null;
  canRefresh: boolean;
  condition: RepositoryCommitLog["condition"] | null;
  repository: RepositoryCommitsRepository;
  actions: RepositoryCommitsActions;
}

export function RepositoryCommitsStatusActions({
  primary,
  secondary,
  canRefresh,
  condition,
  repository,
  actions,
}: RepositoryCommitsStatusActionsProps) {
  const [isConfirmingRebase, setIsConfirmingRebase] = React.useState(false);
  const reasonId = React.useId();
  // Both actions of a status share one access decision, so they share one reason.
  const deniedReason = getDeniedReason(primary ?? secondary);

  const onPress = ({ kind }: CommitLogAction) => {
    switch (kind) {
      case "import":
        return actions.importLatestCommit();
      case "rebase":
        return setIsConfirmingRebase(true);
      case "check":
        return actions.checkRemote();
    }
  };

  return (
    <>
      <Col className="shrink-0 items-start gap-1.5">
        {(canRefresh || secondary || primary) && (
          <Row className="flex-wrap gap-2">
            {canRefresh && <CommitLogRefreshButton repositoryId={repository.id} />}
            {secondary && (
              <CommitLogActionButton
                action={secondary}
                actions={actions}
                describedBy={getDeniedReason(secondary) ? reasonId : undefined}
                onPress={() => onPress(secondary)}
              />
            )}
            {primary && (
              <CommitLogActionButton
                action={primary}
                actions={actions}
                describedBy={getDeniedReason(primary) ? reasonId : undefined}
                onPress={() => onPress(primary)}
                isPrimary
              />
            )}
          </Row>
        )}
        {deniedReason && (
          <p id={reasonId} className="max-w-72 text-foreground-muted text-xs">
            {deniedReason}
          </p>
        )}
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

export function CommitLogRefreshButton({ repositoryId }: { repositoryId: string }) {
  const { currentBranch } = useCurrentBranch();

  return (
    <RefreshButton
      className="rounded-md border-border-strong"
      queryKeys={[
        repositoriesQueryKeys.repository({ repositoryId, branchName: currentBranch.name }),
      ]}
    />
  );
}

interface CommitLogActionButtonProps {
  action: CommitLogAction;
  actions: Pick<RepositoryCommitsActions, "submitting" | "isCheckRunning">;
  describedBy?: string;
  onPress: () => void;
  isPrimary?: boolean;
}

export function CommitLogActionButton({
  action,
  actions,
  describedBy,
  onPress,
  isPrimary = false,
}: CommitLogActionButtonProps) {
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
        isPending={isSubmitting}
        aria-describedby={describedBy}
        onPress={onPress}
      >
        <Icon aria-hidden="true" />
        {isCheckRunning ? "Check running" : ACTION_LABEL[action.kind]}
      </Button>
    </Tooltip>
  );
}

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
          on{" "}
          {defaultBranchName ? <InlineCode>{defaultBranchName}</InlineCode> : "the default branch"}.
          Every change on this branch is rebased: all its data and all its repositories, not only{" "}
          {repositoryName}.
          {mayKeepOwnCommit(condition) &&
            ` If the branch has a commit of its own in ${repositoryName}, the rebase does not replace it.`}
        </>
      }
    />
  );
}

export function InlineCode({ children }: { children: string }) {
  return (
    <code title={children} className="inline-block max-w-64 truncate align-bottom font-mono">
      {children}
    </code>
  );
}
