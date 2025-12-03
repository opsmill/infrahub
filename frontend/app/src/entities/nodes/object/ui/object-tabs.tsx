import { useQueryState } from "nuqs";
import { Link, type LinkProps, useLocation } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import { useGetRelationshipCount } from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count.query";
import type { RelationshipSchema } from "@/entities/schema/types";

export interface ObjectDetailsTabProps extends LinkProps {
  isActive?: boolean;
}

export function ObjectDetailsTab({ isActive, className, ...props }: ObjectDetailsTabProps) {
  return (
    <Link
      ref={(node) => {
        if (isActive) {
          node?.scrollIntoView({ behavior: "smooth" });
        }
      }}
      className={classNames(
        "flex cursor-pointer scroll-m-10 items-center gap-2 whitespace-nowrap border-gray-200 border-b-2 px-1 py-4 font-medium text-sm",
        isActive
          ? "border-custom-blue-500 text-custom-blue-600 dark:border-custom-blue-400 dark:text-custom-blue-400"
          : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:border-gray-500 dark:hover:text-gray-300",
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
  const [qspTab] = useQueryState(QSP.TAB);

  return (
    <ObjectDetailsTab
      isActive={qspTab === relationshipSchema.name}
      to={constructPath(pathname, [{ name: QSP.TAB, value: relationshipSchema.name }])}
      {...props}
    >
      {relationshipSchema.label}
      {isPending && <Spinner />}
      {!isPending && (
        <Badge className="rounded-full font-medium text-gray-80">{relationshipCount}</Badge>
      )}
    </ObjectDetailsTab>
  );
}

export interface TaskTabProps extends Omit<LinkProps, "to"> {
  objectId: string;
}
