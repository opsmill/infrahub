import { GET_PREFIX_KIND } from "@/entities/ipam/api/prefixes";
import { IpDetailsCard } from "@/entities/ipam/common/ip-details-card";
import { constructPathForIpam } from "@/entities/ipam/common/utils";
import { IPAM_ROUTE, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { useCurrentIpNamespace } from "@/entities/ipam/namespaces/ui/ip-namespace-provider";
import { getObjectDetailsPaginated } from "@/entities/nodes/api/getObjectDetails";
import { getPermission } from "@/entities/permission/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import useQuery from "@/shared/api/graphql/useQuery";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router";
import { IpamSummarySkeleton } from "./ipam-summary-skeleton";

export default function IpamIPPrefixesSummaryDetails() {
  const { objectId } = useParams() as { objectId: string };

  const { loading, data } = useQuery(GET_PREFIX_KIND, {
    variables: {
      ids: [objectId],
    },
  });

  if (loading || !data) return <IpamSummarySkeleton />;

  const prefixData = data[IP_PREFIX_GENERIC].edges[0];

  if (!prefixData)
    return <Alert type={ALERT_TYPES.ERROR} message={`Prefix with id ${objectId} not found.`} />;

  const {
    id: prefixId,
    display_label: prefixDisplayLabel,
    __typename: prefixKind,
  } = prefixData.node;

  return (
    <section>
      <header className="flex items-center mb-2">
        <Link to={constructPathForIpam(IPAM_ROUTE.PREFIXES)}>All Prefixes</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span className="font-semibold">{prefixDisplayLabel}</span>
      </header>

      <PrefixSummaryContent prefixId={prefixId} prefixKind={prefixKind} />
    </section>
  );
}

type PrefixSummaryContentProps = {
  prefixId: string;
  prefixKind: string;
};

const PrefixSummaryContent = ({ prefixId, prefixKind }: PrefixSummaryContentProps) => {
  const { currentIpNamespace } = useCurrentIpNamespace();
  const { schema: prefixSchema } = useSchema(prefixKind);

  const columns = prefixSchema
    ? [
        ...(prefixSchema.attributes ?? []).map((attribute) => ({
          isAttribute: true,
          ...attribute,
        })),
        ...(prefixSchema.relationships ?? []).map((relationship) => ({
          isRelationship: true,
          paginated: relationship.cardinality === "many",
          ...relationship,
        })),
      ]
    : [];

  const filters = `ip_namespace__ids: ["${currentIpNamespace.id}"]`;

  const query = gql(
    getObjectDetailsPaginated({
      objectid: prefixId,
      kind: prefixKind,
      columns,
      filters,
      hasPermissions: true,
    })
  );

  const { loading, data, refetch } = useQuery(query, {
    skip: !prefixSchema,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !prefixSchema) return <IpamSummarySkeleton />;

  const prefixData = data[prefixKind]?.edges?.length && data[prefixKind]?.edges[0].node;

  const permission = getPermission(data[prefixKind]?.permissions?.edges);

  if (!prefixData) {
    return <NoDataFound />;
  }

  return (
    <div className="flex flex-wrap items-start gap-2">
      <IpDetailsCard
        schema={prefixSchema}
        data={prefixData}
        refetch={refetch}
        permission={permission}
      />
    </div>
  );
};
