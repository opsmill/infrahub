import { useAtomValue } from "jotai";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Table } from "../../../components/table/table";
import { Pagination } from "../../../components/utils/pagination";
import { IPAM_PREFIX_OBJECT } from "../../../config/constants";
import { GET_PREFIXES } from "../../../graphql/queries/ipam/prefixes";
import useQuery from "../../../hooks/useQuery";
import { schemaState } from "../../../state/atoms/schema.atom";
import { constructPath } from "../../../utils/fetch";
import { getSchemaObjectColumns } from "../../../utils/getSchemaObjectColumns";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP } from "../constants";

export default function IpamIPPrefixesSummaryList() {
  const { prefix } = useParams();
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);
  const schemas = useAtomValue(schemaState);
  const schemaData = schemas.find((schema) => schema.kind === IPAM_PREFIX_OBJECT);
  const columns = getSchemaObjectColumns(schemaData);

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

  const { loading, error, data } = useQuery(GET_PREFIXES, { variables: { prefix: prefix } });

  const rows =
    data &&
    data[IPAM_PREFIX_OBJECT]?.edges.map((edge) => ({
      values: {
        ...edge?.node,
        children_count: edge?.node?.children?.edges?.length,
      },
      link: constructLink(edge?.node),
    }));

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}

      <Pagination count={data && data[IPAM_PREFIX_OBJECT]?.count} />
    </div>
  );
}
