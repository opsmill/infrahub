import type React from "react";

import { NodeLabel } from "@/entities/nodes/object/ui/node-label";

interface AccountEventLayoutProps {
  accountId: string | null;
  branch: string | null;
  children: React.ReactNode;
}

export const AccountEventLayout = ({ accountId, branch, children }: AccountEventLayoutProps) => {
  return (
    <div className="flex w-full min-w-0 items-center gap-1 overflow-hidden text-sm">
      {accountId ? (
        <span className="max-w-50 shrink-0 truncate">
          <NodeLabel id={accountId} kind="CoreAccount" branch={branch} />
        </span>
      ) : (
        "-"
      )}

      {children}
    </div>
  );
};
