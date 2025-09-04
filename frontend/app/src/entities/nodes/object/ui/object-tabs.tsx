import { Link, LinkProps, useLocation } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";

import { QSP } from "@/config/qsp";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";
import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

import { useGetRelationshipCount } from "@/entities/nodes/relationships/domain/get-relationship-count/get-relationship-count.query";
import { RelationshipSchema } from "@/entities/schema/types";

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
        "flex items-center gap-2 whitespace-nowrap border-b-2 border-gray-200 py-4 px-1 text-sm font-medium cursor-pointer scroll-m-10",
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
      {!isPending && (
        <Badge className="font-medium rounded-full text-gray-80">{relationshipCount}</Badge>
      )}
    </ObjectDetailsTab>
  );
}

export interface TaskTabProps extends Omit<LinkProps, "to"> {
  objectId: string;
}
