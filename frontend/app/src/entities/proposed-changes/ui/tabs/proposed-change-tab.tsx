import { useQueryState } from "nuqs";
import { useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Spinner } from "@/shared/components/ui/spinner";
import { QSP } from "@/shared/config/qsp";

import { ObjectDetailsTab } from "@/entities/nodes/object/ui/object-tabs";

export interface ProposedChangeTabProps {
  tabId: string | null;
  label: string;
  count?: number;
  isCountLoading?: boolean;
}

export function ProposedChangeTab({ tabId, label, count, isCountLoading }: ProposedChangeTabProps) {
  const { pathname } = useLocation();
  const [qspTab] = useQueryState(QSP.PROPOSED_CHANGES_TAB);

  const isActive = tabId === null ? !qspTab : qspTab === tabId;
  const to = constructPath(pathname, [
    tabId === null
      ? { name: QSP.PROPOSED_CHANGES_TAB, exclude: true }
      : { name: QSP.PROPOSED_CHANGES_TAB, value: tabId },
  ]);

  return (
    <ObjectDetailsTab isActive={isActive} to={to}>
      {label}
      {isCountLoading && <Spinner className="mx-1" />}
      {!isCountLoading && count !== undefined && (
        <div className="rounded-md bg-gray-100 px-2 py-0.5 text-xs">{count}</div>
      )}
    </ObjectDetailsTab>
  );
}
