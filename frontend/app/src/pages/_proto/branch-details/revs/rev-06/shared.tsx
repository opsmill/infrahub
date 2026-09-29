// PROTOTYPE — pieces both variants share.
import { Card, CardContent, CardHeader } from "@infrahub/ui";
import { BoxIcon, CheckIcon, GitCommitIcon, IdCardIcon, RefreshCwIcon, XIcon } from "lucide-react";

import { DateDisplay } from "@/shared/components/display/date-display";

import type { BranchMock, ProtoData } from "./data";
import type { LocateTarget } from "./locate";
import type { OnLocate } from "./merge-rail";

export type CardControls = {
  page: number;
  onPageChange: (page: number) => void;
  maxBands: number;
  refreshedAt: Date;
  isRefreshing: boolean;
  onRefresh: () => void;
};

export type VariantProps = {
  data: ProtoData;
  locate: LocateTarget | null;
  onLocate: OnLocate;
  card: CardControls;
  tasksPage: number;
  onTasksPage: (page: number) => void;
  railWidth: number;
};

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 truncate text-neutral-500 text-sm">{children}</div>
  );
}

function Value({ children }: { children: React.ReactNode }) {
  return <div className="min-w-0 text-neutral-700 text-sm">{children}</div>;
}

// Today's attributes card, unchanged (the canvas keeps it as-is).
export function Attributes({ branch, title }: { branch: BranchMock; title?: string }) {
  return (
    <Card className={title ? undefined : "w-fit max-w-full"}>
      {title && <CardHeader>{title}</CardHeader>}
      <CardContent className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5">
        <Label>
          <IdCardIcon className="size-3.5" /> Name
        </Label>
        <Value>
          <span className="block truncate">{branch.name}</span>
        </Value>
        <Label>
          <RefreshCwIcon className="size-3.5" /> Sync with Git
        </Label>
        <Value>
          {branch.syncWithGit ? <CheckIcon className="size-4" /> : <XIcon className="size-4" />}
        </Value>
        <Label>
          <BoxIcon className="size-3.5" /> Schema differs from default branch
        </Label>
        <Value>
          {branch.schemaDiffers ? <CheckIcon className="size-4" /> : <XIcon className="size-4" />}
        </Value>
        <Label>
          <GitCommitIcon className="size-3.5" /> Last rebase
        </Label>
        <Value>
          <DateDisplay date={branch.lastRebase} className="text-sm" />
        </Value>
      </CardContent>
    </Card>
  );
}
