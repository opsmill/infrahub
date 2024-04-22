import { forwardRef } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { IPAM_QSP, IPAM_TABS } from "../constants";
import IpamIPAddresses from "../ip-addresses/ipam-ip-address";
import IpamIPPrefixDetails from "./ipam-prefix-details";
import IpamIPPrefixesSummary from "./ipam-prefixes-summary";

const IpamIPPrefixes = forwardRef((props, ref) => {
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);

  switch (qspTab) {
    case IPAM_TABS.PREFIX_DETAILS: {
      return <IpamIPPrefixDetails ref={ref} />;
    }
    case IPAM_TABS.IP_DETAILS: {
      return <IpamIPAddresses ref={ref} />;
    }
    default: {
      return <IpamIPPrefixesSummary ref={ref} />;
    }
  }
});

export default IpamIPPrefixes;
