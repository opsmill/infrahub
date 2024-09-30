import { StringParam, useQueryParam } from "use-query-params";
import { DetailsButtons } from "./details-buttons";
import { QSP } from "@/config/qsp";
import { TASK_TAB } from "@/config/constants";
import { RelationshipsButtons } from "./relationships-buttons";

export function ActionButtons(props: any) {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  if (!qspTab) {
    return <DetailsButtons {...props} />;
  }

  if (qspTab && qspTab !== TASK_TAB) {
    return <RelationshipsButtons {...props} />;
  }

  return null;
}
