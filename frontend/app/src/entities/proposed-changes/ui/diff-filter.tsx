import { parseAsString, useQueryState } from "nuqs";

import { QSP } from "@/config/qsp";

import ErrorScreen from "@/shared/components/errors/error-screen";

import type { GetDiffSummaryParams } from "@/entities/diff/domain/get-diff-summary";
import { useGetDiffSummary } from "@/entities/diff/domain/get-diff-summary.query";
import { DIFF_STATUS, type DiffStatus } from "@/entities/diff/node-diff/types";
import { DiffSummarySkeleton } from "@/entities/proposed-changes/ui/diff-summary/diff-summary-skeleton";
import {
  DiffSummaryTag,
  DiffSummaryTagGroup,
} from "@/entities/proposed-changes/ui/diff-summary/diff-summary-tag-group";

type DiffFilterProps = GetDiffSummaryParams;

export function DiffFilter({ branch, filters }: DiffFilterProps) {
  const [statusFilterQSP, setQsp] = useQueryState(
    QSP.STATUS,
    parseAsString.withOptions({ shallow: false })
  );

  const { error, data, isPending } = useGetDiffSummary({ branch, filters });

  const handleFilter = (value: DiffStatus) => {
    setQsp(value === statusFilterQSP ? null : value);
  };

  if (isPending) {
    return <DiffSummarySkeleton />;
  }

  if (error) {
    return (
      <ErrorScreen
        message={error?.message ?? "No diff summary available."}
        hideIcon
        className="items-start p-0"
      />
    );
  }

  if (!data) {
    return null;
  }

  return (
    <DiffSummaryTagGroup selectionMode="single">
      <DiffSummaryTag
        variant="added"
        count={data.num_added}
        isMuted={!!statusFilterQSP && statusFilterQSP !== DIFF_STATUS.ADDED}
        isClosable={statusFilterQSP === DIFF_STATUS.ADDED}
        onPress={() => handleFilter(DIFF_STATUS.ADDED)}
      />
      <DiffSummaryTag
        variant="removed"
        count={data.num_removed}
        isMuted={!!statusFilterQSP && statusFilterQSP !== DIFF_STATUS.REMOVED}
        isClosable={statusFilterQSP === DIFF_STATUS.REMOVED}
        onPress={() => handleFilter(DIFF_STATUS.REMOVED)}
      />
      <DiffSummaryTag
        variant="updated"
        count={data.num_updated}
        isMuted={!!statusFilterQSP && statusFilterQSP !== DIFF_STATUS.UPDATED}
        isClosable={statusFilterQSP === DIFF_STATUS.UPDATED}
        onPress={() => handleFilter(DIFF_STATUS.UPDATED)}
      />
      <DiffSummaryTag
        variant="conflicts"
        count={data.num_conflicts}
        isMuted={!!statusFilterQSP && statusFilterQSP !== DIFF_STATUS.CONFLICT}
        isClosable={statusFilterQSP === DIFF_STATUS.CONFLICT}
        onPress={() => handleFilter(DIFF_STATUS.CONFLICT)}
      />
    </DiffSummaryTagGroup>
  );
}
