import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Table } from "../../../components/table/table";
import { Link } from "../../../components/utils/link";
import { Pagination } from "../../../components/utils/pagination";
import { IPAM_PREFIX_OBJECT } from "../../../config/constants";
import { GET_PREFIX } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import { schemaState } from "../../../state/atoms/schema.atom";
import { constructPath } from "../../../utils/fetch";
import { getSchemaObjectColumns } from "../../../utils/getSchemaObjectColumns";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP } from "../constants";

export default function IpamIPPrefixDetails() {
  const { prefix } = useParams();
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);
  const schemas = useAtomValue(schemaState);
  const schemaData = schemas.find((schema) => schema.kind === IPAM_PREFIX_OBJECT);
  const columns = getSchemaObjectColumns(schemaData);

  if (!prefix) {
    return <div>Select a prefix</div>;
  }

  const constructLink = (data) => {
    switch (data.__typename) {
      case IPAM_PREFIX_OBJECT: {
        return constructPath(`/ipam/prefixes/${encodeURIComponent(data?.prefix?.value)}`, [
          { name: IPAM_QSP, value: qspTab },
        ]);
      }
      default: {
        return constructPath(`/ipam/ip_address/${encodeURIComponent(data?.prefix?.value)}`, [
          { name: IPAM_QSP, value: qspTab },
        ]);
      }
    }
  };

  const { loading, error, data } = useQuery(GET_PREFIX, { variables: { prefix: prefix } });

  const parent = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.parent?.node;

  const children = data && data[IPAM_PREFIX_OBJECT]?.edges[0]?.node?.children;

  const parentLink = parent?.prefix?.value
    ? constructPath(`/ipam/prefixes/${encodeURIComponent(parent?.prefix?.value)}`, [
        { name: IPAM_QSP, value: qspTab },
      ])
    : constructPath("/ipam/prefixes");

  const rows = children?.edges?.map((child) => ({
    values: {
      ...child?.node,
      children_count: child?.node?.children?.edges?.length,
    },
    link: constructLink(child?.node),
  }));

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      <div className="flex items-center mb-2">
        <Link to={parentLink}>{parent?.display_label ?? "All Prefixes"}</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{prefix}</span>
      </div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}

      <Pagination count={children?.count} />
    </div>
  );
}
