import { IpNamespace } from "@/entities/ipam/namespaces/domain/get-ip-namespace-list";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { Row } from "@/shared/components/container";
import { Badge } from "@/shared/components/ui/badge";
import { Card } from "@/shared/components/ui/card";
import { pluralize } from "@/shared/utils/string";
import { Link } from "react-router";

export interface IpNamespaceCardProps {
  ipNamespace: IpNamespace;
}

export function IpNamespaceCard({ ipNamespace }: IpNamespaceCardProps) {
  return (
    <Link key={ipNamespace.id} to={getObjectDetailsUrl(ipNamespace.__typename, ipNamespace.id)}>
      <Card className="p-4 hover:shadow-md transition-shadow duration-200 flex flex-col gap-2 h-full">
        <h2 className="text-lg font-semibold truncate">{getNodeLabel(ipNamespace)}</h2>
        <Row>
          <Badge className="px-3 py-1.5 bg-blue-50 text-blue-700 font-medium rounded-full">
            {pluralize(ipNamespace.ip_prefixes.count, "Prefix", "es")}
          </Badge>
          <Badge className="px-3 py-1.5 bg-blue-50 text-blue-700 font-medium rounded-full">
            {pluralize(ipNamespace.ip_addresses.count, "Address", "es")}
          </Badge>
          <p className="text-sm text-gray-600">{ipNamespace.description?.value}</p>
        </Row>
      </Card>
    </Link>
  );
}
