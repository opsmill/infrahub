import { forwardRef } from "react";
import { useParams } from "react-router";
import IpamIPPrefixesSummaryDetails from "./ipam-prefixes-summary-details";
import IpamIPPrefixesSummaryList from "./ipam-prefixes-summary-list";

const IpamIPPrefixesSummary = forwardRef((_, ref) => {
  const { prefix } = useParams();

  if (prefix) {
    return <IpamIPPrefixesSummaryDetails />;
  }

  return <IpamIPPrefixesSummaryList ref={ref} />;
});

export default IpamIPPrefixesSummary;
