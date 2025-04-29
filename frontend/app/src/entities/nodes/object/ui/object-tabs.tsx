import { TASK_TAB } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { useGetRelationshipCount } from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count.query";
import { RelationshipSchema } from "@/entities/schema/types";
import { useGetTaskCount } from "@/entities/tasks/domain/get-node-task-count/get-task-count.query";
import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";
import { Link, LinkProps, useLocation } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

export interface ObjectDetailsTabProps extends LinkProps {
  isActive?: boolean;
}

export function ObjectDetailsTab({ isActive, className, ...props }: ObjectDetailsTabProps) {
  return (
    <Link
      className={classNames(
        "flex items-center gap-2 whitespace-nowrap border-b-2 border-gray-200 py-4 px-1 text-sm font-medium cursor-pointer",
        isActive
          ? "border-custom-blue-500 text-custom-blue-600"
          : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
        className
      )}
      {...props}
    />
  );
}

export interface RelationshipTabProps extends Omit<LinkProps, "to"> {
  objectKind: string;
  objectId: string;
  relationshipSchema: RelationshipSchema;
}

export function RelationshipTab({
  objectKind,
  objectId,
  relationshipSchema,
  ...props
}: RelationshipTabProps) {
  const { isPending, data: relationshipCount } = useGetRelationshipCount({
    objectKind,
    objectId,
    relationshipName: relationshipSchema.name,
  });
  const { pathname } = useLocation();
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  return (
    <ObjectDetailsTab
      isActive={qspTab === relationshipSchema.name}
      to={constructPath(pathname, [{ name: QSP.TAB, value: relationshipSchema.name }])}
      {...props}
    >
      {relationshipSchema.label}
      {isPending && <Spinner />}
      <Badge className="font-medium rounded-full text-gray-80">{relationshipCount}</Badge>
    </ObjectDetailsTab>
  );
}

export interface TaskTabProps extends Omit<LinkProps, "to"> {
  objectId: string;
}

export function ObjectTaskTab({ objectId, ...props }: TaskTabProps) {
  const { isPending, data: taskCount } = useGetTaskCount({ nodeId: objectId });
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);

  const { pathname } = useLocation();

  return (
    <ObjectDetailsTab
      isActive={qspTab === TASK_TAB}
      to={constructPath(pathname, [{ name: QSP.TAB, value: TASK_TAB }])}
      {...props}
    >
      Tasks
      {isPending && <Spinner />}
      <Badge className="font-medium rounded-full text-gray-80">{taskCount}</Badge>
    </ObjectDetailsTab>
  );
}
