import { StringParam, useQueryParam } from "use-query-params";

import { TASK_TAB } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constants";

import { DetailsButtons } from "./details-buttons";
import { RelationshipsButtons } from "./relationships-buttons";

export function ActionButtons(props: any) {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  if (!qspTab) {
    return <DetailsButtons {...props} />;
  }

  if (qspTab && qspTab !== TASK_TAB && qspTab !== REPOSITORY_OBJECTS_TAB) {
    return <RelationshipsButtons {...props} />;
  }

  return null;
}
