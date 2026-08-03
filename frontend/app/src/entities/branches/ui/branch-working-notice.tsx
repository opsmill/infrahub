import { Button } from "@infrahub/ui";
import { ArrowLeftRightIcon, GitBranchIcon, TriangleAlertIcon, Undo2Icon } from "lucide-react";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

interface BranchWorkingNoticeProps {
  branch: BranchListItem;
}

export function BranchWorkingNotice({ branch }: BranchWorkingNoticeProps) {
  const { currentBranch, setCurrentBranch } = useCurrentBranch();

  if (currentBranch.name === branch.name) {
    return (
      <BranchNotice
        className="border-cyan-700/20 bg-cyan-700/10 text-cyan-800"
        data-testid="branch-working-notice"
      >
        <GitBranchIcon className="size-4 shrink-0" aria-hidden="true" />
        <p>You're working on this branch.</p>
      </BranchNotice>
    );
  }

  function switchToViewedBranch() {
    const previousBranch = currentBranch;

    setCurrentBranch(branch);
    toast(
      <BranchSwitchedToast
        branchName={branch.name}
        onUndo={() => setCurrentBranch(previousBranch)}
      />
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
  return <Row className={classNames("min-h-10 border-b px-5 text-sm", className)} {...props} />;
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
      <GitBranchIcon className="size-4 shrink-0 text-cyan-700" aria-hidden="true" />
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
