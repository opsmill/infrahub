import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { Link } from "../../../components/utils/link";
import { GET_PREFIX_KIND } from "../../../graphql/queries/ipam/prefixes";
import { getObjectItemsPaginated } from "../../../graphql/queries/objects/getObjectItems";
import useQuery from "../../../hooks/useQuery";
import { genericsState, schemaState } from "../../../state/atoms/schema.atom";
import { getObjectAttributes, getObjectRelationships } from "../../../utils/getSchemaObjectColumns";
import { IpDetailsCard } from "../common/ip-details-card";
import { PrefixUsageChart } from "../common/prefix-usage-chart";
import { IP_PREFIX_GENERIC } from "../constants";
import { IpamSummarySkeleton } from "./ipam-summary-skeleton";

export default function IpamIPPrefixesSummaryDetails() {
  const { prefix } = useParams();

  const { loading, data } = useQuery(GET_PREFIX_KIND, {
    variables: {
      ip: prefix,
    },
  });

  if (loading || !data) return <IpamSummarySkeleton withChart />;

  const prefixKind = data[IP_PREFIX_GENERIC].edges[0].node.__typename;

  return (
    <section>
      <header className="flex items-center mb-2">
        <Link to={"/ipam/prefixes"}>All Prefixes</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix} summary</span>
      </header>

      <PrefixSummaryContent prefixKind={prefixKind} />
    </section>
  );
}

const PrefixSummaryContent = ({ prefixKind }: { prefixKind: string }) => {
  const { prefix } = useParams();
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const prefixSchema = [...nodes, ...generics].find(({ kind }) => kind === prefixKind);

  const attributes = getObjectAttributes(prefixSchema);
  const relationships = getObjectRelationships(prefixSchema);

  const query = gql(
    getObjectItemsPaginated({
      kind: prefixKind,
      attributes,
      relationships,
      filters: `prefix__value: "${prefix}"`,
    })
  );

  const { loading, data } = useQuery(query, {
    skip: !prefixSchema,
    notifyOnNetworkStatusChange: true,
  });

  if (loading || !data || !prefixSchema) return <IpamSummarySkeleton withChart />;

  const prefixData = data[prefixKind].edges[0].node;

  return (
    <div className="flex flex-wrap items-start gap-2">
      <IpDetailsCard schema={prefixSchema} data={prefixData} />
      <PrefixUsageChart usagePercentage={prefixData.utilization.value} />
    </div>
  );
};
