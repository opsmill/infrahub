import { Icon } from "@iconify-icon/react";
import { useRef } from "react";
import { StringParam, useQueryParam } from "use-query-params";

import { TASK_TAB } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import { Link } from "@/shared/components/ui/link";

import { ObjectRelationshipsManager } from "@/entities/nodes/relationships/ui/object-relationships-manager";
import { NodeObject } from "@/entities/nodes/types";
import { REPOSITORY_OBJECTS_TAB } from "@/entities/repository/constant";
import { RepositoryObjectsManager } from "@/entities/repository/ui/repository-objects-manager";
import { ModelSchema } from "@/entities/schema/types";
import { TaskItemDetails } from "@/entities/tasks/ui/task-item-details";
import { TaskItems } from "@/entities/tasks/ui/task-items";

export interface ObjectDetailsTabContentProps {
  objectSchema: ModelSchema;
  objectDetailsData: NodeObject;
}
export function ObjectDetailsTabContent({
  objectSchema,
  objectDetailsData,
}: ObjectDetailsTabContentProps) {
  const { pathname } = location;

  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const [qspTaskId] = useQueryParam(QSP.TASK_ID, StringParam);
  const refetchRef = useRef(null);

  if (!qspTab) {
    return null;
  }

  if (qspTab === REPOSITORY_OBJECTS_TAB) {
    return <RepositoryObjectsManager parentNodeId={objectDetailsData.id} />;
  }

  if (qspTab === TASK_TAB && !qspTaskId) {
    return <TaskItems ref={refetchRef} hideRelatedNode />;
  }

  if (qspTab === TASK_TAB && qspTaskId) {
    return (
      <>
        <div className="flex bg-white text-sm">
          <Link
            to={constructPath(pathname, [
              { name: QSP.TAB, value: TASK_TAB },
              { name: QSP.TASK_ID, exclude: true },
            ])}
            className="flex items-center p-2 "
          >
            <Icon icon={"mdi:chevron-left"} />
            All tasks
          </Link>
        </div>

        <TaskItemDetails ref={refetchRef} />
      </>
    );
  }

  if (qspTab !== TASK_TAB) {
    return (
      <ObjectRelationshipsManager
        parentNodeSchema={objectSchema}
        parentNodeId={objectDetailsData.id}
        relationshipName={qspTab}
      />
    );
  }

  return null;
}
