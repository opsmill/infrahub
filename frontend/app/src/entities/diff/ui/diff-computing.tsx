import { Icon } from "@iconify-icon/react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";

import { DiffRefreshButton } from "@/entities/diff/ui/diff-refresh-button";

export interface DiffComputingProps {
  sourceBranch: string;
  destinationBranch: string;
  hideActions?: boolean;
}

export function DiffComputing({ sourceBranch, destinationBranch, hideActions }: DiffComputingProps) {
  return (
    <div className="mt-10 flex flex-col items-center gap-5">
      <LoadingIndicator message="" />

      <h1 className="inline-flex gap-1.5 font-semibold">
        We are computing the diff between
        <Badge variant="blue">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {sourceBranch}
        </Badge>
        and
        <Badge variant="green">
          <Icon icon="mdi:layers-triple" className="mr-1" />
          {destinationBranch}
        </Badge>
      </h1>

      <div className="text-center">
        <p>This process may take a few seconds to a few minutes.</p>
        <p>Once completed, you&apos;ll be able to view the detailed changes.</p>
      </div>

      {!hideActions && <DiffRefreshButton branchName={sourceBranch} />}
    </div>
  );
}
