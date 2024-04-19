import { Link, useParams } from "react-router-dom";
import { PrefixUsageChart } from "../styled";
import { Icon } from "@iconify-icon/react";

function PrefixSummary() {
  return null;
}

export default function IpamIPPrefixesSummaryDetails() {
  const { prefix } = useParams();

  return (
    <section>
      <header className="flex items-center mb-2">
        <Link to={"/ipam/prefixes"}>All Prefixes</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix} summary</span>
      </header>

      <PrefixSummary />
      <PrefixUsageChart usagePercentage={70} />
    </section>
  );
}
