import { forwardRef } from "react";
import { useParams } from "react-router-dom";
import IpamIPPrefixesSummaryDetails from "./ipam-prefixes-summary-details";
import IpamIPPrefixesSummaryList from "./ipam-prefixes-summary-list";

const IpamIPPrefixesSummary = forwardRef((props, ref) => {
  const { prefix } = useParams();

  if (prefix) {
    return <IpamIPPrefixesSummaryDetails />;
  }

  return <IpamIPPrefixesSummaryList ref={ref} />;
});

export default IpamIPPrefixesSummary;
