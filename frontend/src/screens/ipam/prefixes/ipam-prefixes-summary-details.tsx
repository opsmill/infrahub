import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { Link } from "../../../components/utils/link";

export default function IpamIPPrefixesSummaryDetails() {
  const { prefix } = useParams();
  return (
    <div>
      <div className="flex items-center mb-2">
        <Link to={"/ipam/prefixes"}>All Prefixes</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix} summary</span>
      </div>
    </div>
  );
}
