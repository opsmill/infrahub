import { Link } from "react-router";

import { Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import type { IpNamespace } from "@/entities/ipam/ip-namespaces/domain/get-ip-namespace-list";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export interface IpNamespaceCardProps {
  ipNamespace: IpNamespace;
}

const CARD_STYLES = {
  container: classNames(
    "bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-2",
    "transition-all hover:border-custom-blue-600 hover:shadow-sm",
    focusVisibleStyle
  ),
  title: "text-lg font-semibold truncate",
  badge: "px-3 py-1.5 bg-blue-50 text-blue-700 font-medium rounded-full",
  description: "text-sm text-gray-600",
};

export function IpNamespaceCard({ ipNamespace }: IpNamespaceCardProps) {
  const { id, __typename, description, ip_prefixes, ip_addresses } = ipNamespace;
  const detailsUrl = getObjectDetailsUrl(__typename, id);
  const nodeLabel = getNodeLabel(ipNamespace);

  return (
    <Link to={detailsUrl} className={CARD_STYLES.container}>
      <h2 className={CARD_STYLES.title}>{nodeLabel}</h2>
      <Row>
        <Badge className={CARD_STYLES.badge}>{pluralize(ip_prefixes.count, "Prefix", "es")}</Badge>
        <Badge className={CARD_STYLES.badge}>
          {pluralize(ip_addresses.count, "Address", "es")}
        </Badge>
        <p className={CARD_STYLES.description}>{description?.value}</p>
      </Row>
    </Link>
  );
}
