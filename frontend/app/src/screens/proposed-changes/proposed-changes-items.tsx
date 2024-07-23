import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Badge } from "@/components/ui/badge";
import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { getProposedChanges } from "@/graphql/queries/proposed-changes/getProposedChanges";
import { usePermission } from "@/hooks/usePermission";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import { schemaState } from "@/state/atoms/schema.atom";
import { getObjectRelationships } from "@/utils/getSchemaObjectColumns";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Table } from "@/components/table/table";
import { ProposedChangesData } from "@/screens/proposed-changes/proposed-changes-data";
import { ProposedChangesInfo } from "@/screens/proposed-changes/proposed-changes-info";
import { Card } from "@/components/ui/card";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { debounce } from "@/utils/common";
import { TabsButtons } from "@/components/buttons/tabs-buttons";
import { useNavigate } from "react-router-dom";
import { constructPath } from "@/utils/fetch";
import { QSP } from "@/config/qsp";
import { StringParam, useQueryParam } from "use-query-params";
import { ProposedChangesReviewers } from "./proposed-changes-reviewers";

export const ProposedChangesPage = () => {
  const [schemaList] = useAtom(schemaState);
  const permission = usePermission();
  const navigate = useNavigate();
  const [qspState] = useQueryParam(QSP.PROPOSED_CHANGES_STATE, StringParam);
  useTitle("Proposed changes list");

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);
  const accountSchemaData = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);
  const relationships = getObjectRelationships({ schema: schemaData, forListView: true });

  const queryString = schemaData
    ? getProposedChanges({
        kind: schemaData.kind,
        accountKind: accountSchemaData?.kind,
        attributes: schemaData.attributes,
        relationships,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schemaData
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const {
    loading,
    error,
    data = {},
    refetch,
  } = useQuery(query, {
    variables: { state: qspState },
    skip: !schemaData,
    notifyOnNetworkStatusChange: true,
  });

  const handleRefetch = () => refetch();

  const result = data && schemaData?.kind ? data[schemaData?.kind] ?? {} : {};

  const { count = "...", edges = [] } = result;

  const nodes = edges?.map((edge: any) => edge.node).reverse();

  const handleDelete = () => {};

  const handleSearch: SearchInputProps["onChange"] = (e) => {
    const value = e.target.value as string;
    console.log("value: ", value);
  };

  const debouncedHandleSearch = debounce(handleSearch, 500);

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the proposed changes list." />;
  }

  const columns = [
    {
      name: "name",
      label: "Name",
    },
    {
      name: "data",
      label: "Data",
    },
    {
      name: "checks",
      label: "Checks",
    },
    {
      name: "tasks",
      label: "Tasks",
    },
    {
      name: "artifacts",
      label: "Artifacts",
    },
    {
      name: "reviewers",
      label: "Reviewers",
    },
  ];

  const rows = nodes.map((node: any) => {
    return {
      link: constructPath(`/proposed-changes/${node.id}`),
      values: {
        name: (
          <ProposedChangesInfo
            name={node.display_label}
            branch={node.source_branch.value}
            date={node._updated_at}
          />
        ),
        data: <ProposedChangesData />,
        checks: <Badge className="rounded-full">0</Badge>,
        tasks: <Badge className="rounded-full">0</Badge>,
        artifacts: <Badge className="rounded-full">0</Badge>,
        reviewers: (
          <ProposedChangesReviewers
            reviewers={node.reviewers.edges.map((edge: any) => edge.node)}
            approved_by={node.approved_by.edges.map((edge: any) => edge.node)}
          />
        ),
      },
    };
  });

  const tabs = [
    {
      label: "Opened",
      name: "opene",
    },
    {
      label: "Closed",
      name: "close",
    },
  ];

  return (
    <Content>
      <Content.Title
        title={
          <>
            Proposed changes <Badge>{count}</Badge>
          </>
        }
        reload={handleRefetch}
        isReloadLoading={loading}></Content.Title>

      <Card className="m-2">
        <div className="flex items-center mb-2 gap-2">
          <SearchInput
            loading={loading}
            onChange={debouncedHandleSearch}
            placeholder="Search a Propsoed Change"
            className="border-none focus-visible:ring-0 h-7"
            containerClassName=" flex-grow"
            data-testid="proposed-changes-list-search-bar"
          />

          <TabsButtons tabs={tabs} qsp={QSP.PROPOSED_CHANGES_STATE} />

          <ButtonWithTooltip
            disabled={!permission.write.allow}
            tooltipEnabled={!permission.write.allow}
            tooltipContent={permission.write.message ?? undefined}
            onClick={() => navigate(constructPath("/proposed-changes/new"))}
            className="mr-4"
            data-testid="create-object-button">
            <Icon icon="mdi:plus" className="text-sm" />
            Add {schemaData?.label}
          </ButtonWithTooltip>
        </div>

        <Table columns={columns} rows={rows} onDelete={handleDelete} />
      </Card>
    </Content>
  );
};
