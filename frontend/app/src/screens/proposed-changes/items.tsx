import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Badge } from "@/components/ui/badge";
import { usePermission } from "@/hooks/usePermission";
import useQuery, { useMutation } from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import { Icon } from "@iconify-icon/react";
import { Table, tRow } from "@/components/table/table";

import { CardWithBorder } from "@/components/ui/card";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { debounce } from "@/utils/common";
import { TabsButtons } from "@/components/buttons/tabs-buttons";
import { useNavigate } from "react-router-dom";
import { constructPath } from "@/utils/fetch";
import { QSP } from "@/config/qsp";
import { ProposedChangesDiffSummary } from "./diff-summary";
import { useState } from "react";
import ModalDelete from "@/components/modals/modal-delete";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { DELETE_PROPOSED_CHANGE } from "@/graphql/mutations/proposed-changes/deleteProposedChange";
import { GET_PROPOSED_CHANGES } from "@/graphql/queries/proposed-changes/getProposedChanges";
import { ARTIFACT_OBJECT, PROPOSED_CHANGES_OBJECT, TASK_OBJECT } from "@/config/constants";
import { ProposedChangesInfo } from "@/screens/proposed-changes/item-info";
import { ProposedChangesCounter } from "@/screens/proposed-changes/counter";
import { getProposedChangesTasks } from "@/graphql/queries/proposed-changes/getProposedChangesTasks";
import { getProposedChangesArtifacts } from "@/graphql/queries/proposed-changes/getProposedChangesArtifacts";
import { ProposedChangesReviewers } from "@/screens/proposed-changes/reviewers";
import { NetworkStatus } from "@apollo/client";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { StringParam, useQueryParam } from "use-query-params";

const STATES = {
  open: ["open"],
  close: ["closed", "merged", "canceled"],
};

export const ProposedChangesPage = () => {
  const permission = usePermission();
  const navigate = useNavigate();
  const [qspState] = useQueryParam(QSP.PROPOSED_CHANGES_STATE, StringParam);
  useTitle("Proposed changes");
  const [search, setSearch] = useQueryParam(QSP.SEARCH, StringParam);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<tRow | undefined>();

  const states = qspState ? STATES[qspState] : STATES.open;

  const { loading, networkStatus, previousData, error, data, refetch } = useQuery(
    GET_PROPOSED_CHANGES,
    {
      variables: { states, search },
      notifyOnNetworkStatusChange: true,
    }
  );
  const [deleteProposedChange, { loading: isDeleteLoading }] = useMutation(DELETE_PROPOSED_CHANGE);

  if (error) {
    return (
      <ErrorScreen message="Something went wrong when fetching proposed changes. Try reloading the page." />
    );
  }

  if (networkStatus === NetworkStatus.loading && !data) {
    return <LoadingScreen />;
  }

  const proposedChangesData = (data || previousData)?.[PROPOSED_CHANGES_OBJECT];
  if (!proposedChangesData) {
    return (
      <ErrorScreen message="Something went wrong when displaying proposed changes. Try reloading the page." />
    );
  }

  const nodes = proposedChangesData.edges?.map((edge) => edge?.node).reverse() ?? [];

  const submitDeleteProposedChange = async () => {
    if (!relatedRowToDelete?.values?.id) return;

    try {
      await deleteProposedChange({ variables: { id: relatedRowToDelete.values.id } });

      await refetch();

      setRelatedRowToDelete(undefined);

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`Proposed changes '${relatedRowToDelete?.values?.display_label}' deleted`}
        />
      );
    } catch (error) {
      console.error("Error while deleting proposed change:", error);
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message="An error occurred while deleting the proposed changes"
        />
      );
    }
  };

  const handleSearch: SearchInputProps["onChange"] = (e) => {
    const value = e.target.value;
    setSearch(value);
  };

  const debouncedHandleSearch = debounce(handleSearch, 500);

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
      name: "open",
    },
    {
      label: "Closed",
      name: "close",
    },
  ];

  return (
    <>
      <Content.Title
        title={
          <div className="flex items-center gap-2">
            Proposed changes <Badge>{proposedChangesData?.count ?? "..."}</Badge>
          </div>
        }
        reload={() => refetch()}
        isReloadLoading={loading}
      />

      <Content>
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
              New proposed change
            </ButtonWithTooltip>
          </div>

          <Table
            columns={columns}
            rows={rows}
            onDelete={(row) => setRelatedRowToDelete(row)}
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
            onDelete={submitDeleteProposedChange}
            open={!!relatedRowToDelete}
            setOpen={() => setRelatedRowToDelete(undefined)}
            isLoading={isDeleteLoading}
          />
        )}
      </Content>
    </>
  );
};
