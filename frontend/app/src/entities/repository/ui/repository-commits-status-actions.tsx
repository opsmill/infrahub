import { Button, Sheet, Tooltip } from "@infrahub/ui";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLineIcon,
  ArrowUpRightIcon,
  GitBranchIcon,
  type LucideIcon,
  PencilIcon,
  RadarIcon,
  RefreshCwIcon,
} from "lucide-react";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import { getBranchDetailsUrl } from "@/entities/branches/ui/routing/branch-urls";
import ObjectEdit from "@/entities/nodes/object/ui/object-edit/object-item-edit-paginated";
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
import { getTaskDetailsUrl } from "@/entities/tasks/ui/routing/task-urls";

const ACTION_LABEL: Record<CommitLogActionKind, string> = {
  import: "Import latest commit",
  rebase: "Rebase branch",
  check: "Check remote now",
  refresh: "Refresh",
  "change-ref": "Change tracked ref",
};

const ACTION_ICON: Record<CommitLogActionKind, LucideIcon> = {
  import: ArrowDownToLineIcon,
  rebase: GitBranchIcon,
  check: RadarIcon,
  refresh: RefreshCwIcon,
  "change-ref": PencilIcon,
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
  const [isEditing, setIsEditing] = React.useState(false);
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
      case "change-ref":
        return setIsEditing(true);
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
        <RemoteCheckStatus taskId={actions.runningCheckTaskId} />
      </Col>
      <RebaseConfirm
        condition={condition}
        repositoryName={repository.name}
        isOpen={isConfirmingRebase}
        onOpenChange={setIsConfirmingRebase}
        isLoading={actions.submitting === "rebase"}
        onConfirm={() => actions.rebaseBranch({ onSettled: () => setIsConfirmingRebase(false) })}
      />
      <Sheet isOpen={isEditing} onOpenChange={setIsEditing}>
        <SlideOverTitle
          schema={repository.schema}
          currentObjectLabel={repository.name}
          title={`Edit ${repository.name}`}
          subtitle={repository.schema.description}
        />
        <ObjectEdit
          closeDrawer={() => setIsEditing(false)}
          onUpdateComplete={async () => {
            // invalidation-at-callsite: a new tracked ref changes the repository data, which the object update does not refresh.
            await queryClient.invalidateQueries({ queryKey: repositoriesQueryKeys.all });
            setIsEditing(false);
          }}
          objectId={repository.id}
          objectKind={repository.schema.kind}
        />
      </Sheet>
    </>
  );
}

interface CommitLogActionButtonProps {
  action: CommitLogAction;
  actions: Pick<RepositoryCommitsActions, "submitting" | "runningCheckTaskId">;
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
  const isCheckRunning = action.kind === "check" && actions.runningCheckTaskId !== null;
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

export function RemoteCheckStatus({ taskId }: { taskId: string | null }) {
  return (
    <p role="status" className="flex items-center gap-1 text-foreground-muted text-xs">
      {taskId && (
        <>
          Check running.
          <InternalLink to={getTaskDetailsUrl(taskId)} className="text-xs">
            View task
          </InternalLink>
        </>
      )}
    </p>
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
      isCancelFocusedOnOpen
      description={
        <>
          <span className="break-all font-semibold text-foreground">{branchName}</span> is rebased
          on {defaultBranchName ? <Ref>{defaultBranchName}</Ref> : "the default branch"}. Every
          change on this branch is rebased: all its data and all its repositories, not only{" "}
          {repositoryName}.
          {mayKeepOwnCommit &&
            ` If the branch has a commit of its own in ${repositoryName}, the rebase does not replace it.`}{" "}
          <Link to={getBranchDetailsUrl(branchName)} className="underline">
            Open the branch page
          </Link>{" "}
          to review the branch first.
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

const LINK_CLASS_NAME =
  "group inline-flex min-w-0 items-center gap-1 rounded-sm text-accent no-underline text-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring-halo";

const LINK_LABEL_CLASS_NAME = "min-w-0 truncate underline-offset-2 group-hover:underline";

export function InternalLink({
  to,
  className,
  children,
}: {
  to: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link to={to} className={classNames(LINK_CLASS_NAME, className)}>
      <span className={LINK_LABEL_CLASS_NAME}>{children}</span>
      <ArrowUpRightIcon className="size-3.5 shrink-0" aria-hidden="true" />
    </Link>
  );
}

export function ExternalLink({
  href,
  icon: Icon,
  children,
}: {
  href: string;
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={LINK_CLASS_NAME}>
      <span className={LINK_LABEL_CLASS_NAME}>{children}</span>
      <span className="sr-only">(opens in a new tab)</span>
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
    </a>
  );
}
