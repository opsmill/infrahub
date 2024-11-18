import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { Link } from "@/components/ui/link";
import { GET_PREFIX_KIND } from "@/graphql/queries/ipam/prefixes";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import useQuery from "@/hooks/useQuery";
import NoDataFound from "@/screens/errors/no-data-found";
import { IpDetailsCard } from "@/screens/ipam/common/ip-details-card";
import { constructPathForIpam } from "@/screens/ipam/common/utils";
import { IPAM_QSP, IPAM_ROUTE, IP_PREFIX_GENERIC } from "@/screens/ipam/constants";
import { getPermission } from "@/screens/permission/utils";
import { genericsState, schemaState } from "@/state/atoms/schema.atom";
import { getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { IpamSummarySkeleton } from "./ipam-summary-skeleton";

export default function IpamIPPrefixesSummaryDetails() {
  const { prefix } = useParams() as { prefix: string };

  const { loading, data } = useQuery(GET_PREFIX_KIND, {
    variables: {
      ids: [prefix],
    },
  });

  if (loading || !data) return <IpamSummarySkeleton />;

  const prefixData = data[IP_PREFIX_GENERIC].edges[0];

  if (!prefixData)
    return <Alert type={ALERT_TYPES.ERROR} message={`Prefix with id ${prefix} not found.`} />;

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
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const [namespace] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);

  const prefixSchema = [...nodes, ...generics].find(({ kind }) => kind === prefixKind);

  const columns = getSchemaObjectColumns({ schema: prefixSchema });

  const filters = namespace ? `ip_namespace__ids: ["${namespace}"]` : "";

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
