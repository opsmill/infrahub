import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Badge } from "@/components/ui/badge";
import { ARTIFACT_OBJECT, PROPOSED_CHANGES_OBJECT, TASK_OBJECT } from "@/config/constants";
import { getProposedChanges } from "@/graphql/queries/proposed-changes/getProposedChanges";
import { usePermission } from "@/hooks/usePermission";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import { schemaState } from "@/state/atoms/schema.atom";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue } from "jotai";
import { Table } from "@/components/table/table";

import { CardWithBorder } from "@/components/ui/card";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { debounce } from "@/utils/common";
import { TabsButtons } from "@/components/buttons/tabs-buttons";
import { useNavigate } from "react-router-dom";
import { constructPath } from "@/utils/fetch";
import { QSP } from "@/config/qsp";
import { StringParam, useQueryParam } from "use-query-params";
import { ProposedChangesReviewers } from "./reviewers";
import { ProposedChangesInfo } from "./item-info";
import { ProposedChangesDiffSummary } from "./diff-summary";
import { ProposedChangesCounter } from "./counter";
import { getProposedChangesTasks } from "@/graphql/queries/proposed-changes/getProposedChangesTasks";
import { getProposedChangesArtifacts } from "@/graphql/queries/proposed-changes/getProposedChangesArtifacts";
import { useState } from "react";
import ModalDelete from "@/components/modals/modal-delete";
import { deleteObject } from "@/graphql/mutations/objects/deleteObject";
import { stringifyWithoutQuotes } from "@/utils/string";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { currentBranchAtom } from "@/state/atoms/branches.atom";

export const ProposedChangesPage = () => {
  const [schemaList] = useAtom(schemaState);
  const permission = usePermission();
  const navigate = useNavigate();
  const [qspState] = useQueryParam(QSP.PROPOSED_CHANGES_STATE, StringParam);
  useTitle("Proposed changes");
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [search, setSearch] = useQueryParam(QSP.LIST_SEARCH, StringParam);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState();

  const schemaData = schemaList.find((s) => s.kind === PROPOSED_CHANGES_OBJECT);

  const query = gql`
    ${getProposedChanges}
  `;

  const {
    loading,
    error,
    data = {},
    refetch,
  } = useQuery(query, {
    variables: { state: qspState, search },
    skip: !schemaData,
    notifyOnNetworkStatusChange: true,
  });

  const handleRefetch = () => refetch();

  const result = data && schemaData?.kind ? data[schemaData?.kind] ?? {} : {};

  const { count = "...", edges = [] } = result;

  const nodes = edges?.map((edge: any) => edge.node).reverse();

  const handleDeleteObject = async () => {
    if (!relatedRowToDelete?.values?.id) {
      return;
    }

    setIsLoading(true);

    try {
      const mutationString = deleteObject({
        kind: PROPOSED_CHANGES_OBJECT,
        data: stringifyWithoutQuotes({
          id: relatedRowToDelete?.values?.id,
        }),
      });

      const mutation = gql`
        ${mutationString}
      `;

      await graphqlClient.mutate({
        mutation,
        context: { branch: branch?.name, date },
      });

      refetch();

      setRelatedRowToDelete(undefined);

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Proposed changes '${relatedRowToDelete?.values?.display_label}' deleted`}
        />
      );
    } catch (error) {
      console.error("Error while deleting address: ", error);
    }

    setIsLoading(false);
  };

  const handleDelete = (data: any) => {
    setRelatedRowToDelete(data);
  };

  const handleSearch: SearchInputProps["onChange"] = (e) => {
    const value = e.target.value as string;
    setSearch(value);
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
        id: node.id, // Used for delete modal
        display_label: node.display_label, // Used for delete modal
        name: (
          <ProposedChangesInfo
            name={node.display_label}
            branch={node.source_branch.value}
            date={node._updated_at}
            comments={node.comments.count}
          />
        ),
        data: <ProposedChangesDiffSummary branch={node.source_branch.value} />,
        checks: <Badge className="rounded-full">{node.validations.count}</Badge>,
        tasks: (
          <ProposedChangesCounter id={node.id} query={getProposedChangesTasks} kind={TASK_OBJECT} />
        ),
        artifacts: (
          <ProposedChangesCounter
            id={node.id}
            query={getProposedChangesArtifacts}
            kind={ARTIFACT_OBJECT}
          />
        ),
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
        isReloadLoading={loading}
      />
      <CardWithBorder className="m-2">
        <div className="flex items-center m-2 gap-2">
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
            data-testid="add-proposed-changes-button">
            <Icon icon="mdi:plus" className="text-sm" />
            Add {schemaData?.label}
          </ButtonWithTooltip>
        </div>

        <Table
          columns={columns}
          rows={rows}
          onDelete={handleDelete}
          className="border-0 border-t"
        />
      </CardWithBorder>

      {relatedRowToDelete && (
        <ModalDelete
          title="Delete"
          description={
            <>
              Are you sure you want to delete the Proposed Change:{" "}
              <b>{relatedRowToDelete?.values?.display_label}</b>
            </>
          }
          onCancel={() => setRelatedRowToDelete(undefined)}
          onDelete={handleDeleteObject}
          open={!!relatedRowToDelete}
          setOpen={() => setRelatedRowToDelete(undefined)}
          isLoading={isLoading}
        />
      )}
    </Content>
  );
};
