import { useParams } from "react-router-dom";
import IpamIPPrefixesSummaryDetails from "./ipam-prefixes-summary-details";
import IpamIPPrefixesSummaryList from "./ipam-prefixes-summary-list";

export default function IpamIPPrefixesSummary() {
  const { prefix } = useParams();

  if (prefix) {
    return <IpamIPPrefixesSummaryDetails />;
  }

  return <IpamIPPrefixesSummaryList />;
}
