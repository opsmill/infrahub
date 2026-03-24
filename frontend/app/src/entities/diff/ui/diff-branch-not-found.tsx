import { Icon } from "@iconify-icon/react";

const BRANCH_NOT_FOUND_REGEX = /^Branch: .+ not found\.$/;

export function isBranchNotFoundError(error: Error): boolean {
  return BRANCH_NOT_FOUND_REGEX.test(error.message);
}

interface DiffBranchNotFoundProps {
  branchName: string;
}

export function DiffBranchNotFound({ branchName }: DiffBranchNotFoundProps) {
  return (
    <div className="my-10 flex flex-col items-center gap-5">
      <div className="inline-flex rounded-full bg-white p-3">
        <Icon icon="mdi:source-branch-remove" className="text-2xl text-red-400" />
      </div>

      <h1 className="font-semibold text-lg">Branch not available</h1>
      <p className="text-center text-gray-600">
        The branch <span className="font-semibold">{branchName}</span> has been deleted and its diff
        data is no longer available.
      </p>
    </div>
  );
}
