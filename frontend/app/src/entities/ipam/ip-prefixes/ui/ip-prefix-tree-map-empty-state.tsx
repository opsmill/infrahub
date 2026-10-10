import { Meter } from "@infrahub/ui";

import { Col } from "@/shared/components/container";
import { Link } from "@/shared/components/ui/link";

import { constructPathForIpam } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";

export interface IpPrefixTreeMapEmptyStateProps {
  utilization: number | null;
}

export function IpPrefixTreeMapEmptyState({ utilization }: IpPrefixTreeMapEmptyStateProps) {
  return (
    <Col
      data-testid="ip-prefix-tree-map-empty"
      className="items-center justify-center gap-3 py-12 text-foreground-muted"
    >
      {utilization !== null && (
        <div className="w-40">
          <Meter value={utilization} aria-label="Utilization" />
        </div>
      )}
      <p className="text-sm">This prefix holds IP addresses. The tree map shows child prefixes.</p>
      {/* The tab lives on the parent route, so the link climbs out of the tree-map segment */}
      <Link to={constructPathForIpam("../ip_addresses")} className="text-sm">
        IP Addresses
      </Link>
    </Col>
  );
}
