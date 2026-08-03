import { Button } from "@infrahub/ui";
import { ArrowLeftRightIcon, GitBranchIcon, TriangleAlertIcon, Undo2Icon } from "lucide-react";
import { toast } from "react-toastify";

import { classNames } from "@/shared/utils/common";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { useSwitchBranch } from "@/entities/branches/ui/hooks/use-switch-branch";

interface BranchWorkingNoticeProps {
  branch: BranchListItem;
}

export function BranchWorkingNotice({ branch }: BranchWorkingNoticeProps) {
  const { currentBranch, switchBranch } = useSwitchBranch();

  if (currentBranch.name === branch.name) {
    return (
      <BranchNotice
        className="border-custom-blue-700/20 bg-custom-blue-700/10 text-custom-blue-800"
        data-testid="branch-working-notice"
      >
        <GitBranchIcon className="size-4 shrink-0" aria-hidden="true" />
        <p>You're working on this branch.</p>
      </BranchNotice>
    );
  }

  function switchToViewedBranch() {
    const previousBranch = currentBranch;

    switchBranch(branch);
    toast(
      <BranchSwitchedToast branchName={branch.name} onUndo={() => switchBranch(previousBranch)} />
    );
  }

  return (
    <BranchNotice
      className="border-amber-200 bg-amber-50 text-amber-800"
      data-testid="branch-mismatch-notice"
    >
      <TriangleAlertIcon className="size-4 shrink-0" aria-hidden="true" />
      <p>
        You're viewing <span className="font-semibold">{branch.name}</span> but working on{" "}
        <span className="font-semibold">{currentBranch.name}</span>.
      </p>

      <Button
        variant="outline"
        size="xs"
        className="ml-auto shrink-0"
        onPress={switchToViewedBranch}
        data-testid="switch-to-viewed-branch"
      >
        <ArrowLeftRightIcon />
        Switch to this branch
      </Button>
    </BranchNotice>
  );
}

interface BranchNoticeProps extends React.HTMLAttributes<HTMLDivElement> {}

function BranchNotice({ className, ...props }: BranchNoticeProps) {
  return (
    <div
      // min-h holds both states at the same height so switching doesn't shift the page below.
      className={classNames(
        "flex min-h-12 items-center gap-2.5 border-b px-5 py-2 text-sm",
        className
      )}
      {...props}
    />
  );
}

interface BranchSwitchedToastProps {
  branchName: string;
  onUndo: () => void;
  /** Injected by react-toastify into the rendered toast content. */
  closeToast?: () => void;
}

function BranchSwitchedToast({ branchName, onUndo, closeToast }: BranchSwitchedToastProps) {
  function undo() {
    onUndo();
    closeToast?.();
  }

  return (
    // ToastContainer sets no theme, so .Toastify__toast falls back to white text: set it explicitly.
    <div className="flex items-center gap-2.5 p-2 text-sm text-stone-800">
      <GitBranchIcon className="size-4 shrink-0 text-custom-blue-700" aria-hidden="true" />
      <p>
        Now working on <span className="font-semibold">{branchName}</span>
      </p>

      <Button
        variant="ghost"
        size="xxs"
        className="ml-auto"
        onPress={undo}
        data-testid="undo-branch-switch"
      >
        <Undo2Icon />
        Undo
      </Button>
    </div>
  );
}
