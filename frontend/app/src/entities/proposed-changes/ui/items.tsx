import useQuery, { useMutation } from "@/shared/api/graphql/useQuery";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { Table, tRow } from "@/shared/components/table/table";
import { Badge } from "@/shared/components/ui/badge";
import { useTitle } from "@/shared/hooks/useTitle";
import { Icon } from "@iconify-icon/react";

import { ARTIFACT_OBJECT, PROPOSED_CHANGES_OBJECT, TASK_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { DELETE_PROPOSED_CHANGE } from "@/entities/proposed-changes/api/deleteProposedChange";
import { GET_PROPOSED_CHANGES } from "@/entities/proposed-changes/api/getProposedChanges";
import { getProposedChangesArtifacts } from "@/entities/proposed-changes/api/getProposedChangesArtifacts";
import { getProposedChangesTasks } from "@/entities/proposed-changes/api/getProposedChangesTasks";
import { ProposedChangesCounter } from "@/entities/proposed-changes/ui/counter";
import { ProposedChangeDiffSummary } from "@/entities/proposed-changes/ui/diff-summary";
import { ProposedChangesInfo } from "@/entities/proposed-changes/ui/item-info";
import { ProposedChangesReviewers } from "@/entities/proposed-changes/ui/reviewers";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { constructPath } from "@/shared/api/rest/fetch";
import { TabsButtons } from "@/shared/components/buttons/tabs-buttons";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ObjectHelpButton } from "@/shared/components/menu/object-help-button";
import ModalDelete from "@/shared/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { SearchInput, SearchInputProps } from "@/shared/components/ui/search-input";
import { classNames, debounce } from "@/shared/utils/common";
import { NetworkStatus } from "@apollo/client";
import { useState } from "react";
import { Link, LinkProps, useNavigate } from "react-router";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { getPermission } from "../../permission/utils";

const STATES = {
  open: ["open", "merging"],
  close: ["closed", "merged", "canceled"],
};

export const ProposedChangesPage = () => {
  const navigate = useNavigate();
  const [qspState] = useQueryParam(QSP.PROPOSED_CHANGES_STATE, StringParam);
  useTitle("Proposed changes");
  const [search, setSearch] = useQueryParam(QSP.SEARCH, StringParam);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<tRow | undefined>();
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT);

  const {
    loading,
    networkStatus,
    previousData,
    error,
    data: latestData,
    refetch,
  } = useQuery(GET_PROPOSED_CHANGES, {
    variables: {
      statesVisible: qspState === "close" ? STATES.close : STATES.open,
      search,
    },
    notifyOnNetworkStatusChange: true,
  });
  const [deleteProposedChange, { loading: isDeleteLoading }] = useMutation(DELETE_PROPOSED_CHANGE);

  const data = latestData || previousData;
  const permission = getPermission(data?.[PROPOSED_CHANGES_OBJECT]?.permissions?.edges);

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return (
      <ErrorScreen message="Something went wrong when fetching proposed changes. Try reloading the page." />
    );
  }

  if (networkStatus === NetworkStatus.loading && !data) {
    return <LoadingIndicator className="h-full" />;
  }

  const proposedChangesData = data?.[PROPOSED_CHANGES_OBJECT];
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
    const proposedChangeDetailsPath = `/proposed-changes/${node.id}`;

    const PcDetailsLink = ({
      tab,
      ...props
    }: Omit<LinkProps, "to"> & {
      tab?: "data" | "artifacts" | "schema" | "checks" | "tasks";
    }) => (
      <Link
        {...props}
        className="w-full min-h-[64px] flex items-center"
        to={constructPath(
          proposedChangeDetailsPath,
          tab && [{ name: QSP.PROPOSED_CHANGES_TAB, value: tab }]
        )}
      />
    );

    return {
      link: constructPath(proposedChangeDetailsPath),
      values: {
        id: node.id, // Used for delete modal
        display_label: node.display_label, // Used for delete modal
        name: {
          display: (
            <ProposedChangesInfo
              name={node.display_label}
              branch={node.source_branch.value}
              date={node._updated_at}
              comments={node.comments.count}
              checks={node.validations.edges.map(({ node }: any) => node)}
            />
          ),
        },
        data: {
          display: (
            <PcDetailsLink tab="data">
              <ProposedChangeDiffSummary
                proposedChangeId={node.id}
                branchName={node.source_branch.value}
              />
            </PcDetailsLink>
          ),
        },
        checks: {
          display: (
            <PcDetailsLink tab="checks">
              <Badge className="rounded-full px-2">{node.validations.count}</Badge>
            </PcDetailsLink>
          ),
        },
        tasks: {
          display: (
            <PcDetailsLink tab="tasks">
              <ProposedChangesCounter
                id={node.id}
                query={getProposedChangesTasks}
                kind={TASK_OBJECT}
              />
            </PcDetailsLink>
          ),
        },
        artifacts: {
          display: (
            <PcDetailsLink tab="artifacts">
              <ProposedChangesCounter
                id={node.id}
                query={getProposedChangesArtifacts}
                kind={ARTIFACT_OBJECT}
              />
            </PcDetailsLink>
          ),
        },
        reviewers: {
          display: (
            <ProposedChangesReviewers
              reviewers={node.reviewers.edges.map((edge: any) => edge.node)}
              approved_by={node.approved_by.edges.map((edge: any) => edge.node)}
            />
          ),
        },
      },
    };
  });

  const tabs = [
    {
      label: (
        <>
          Opened
          <Badge className={classNames("ml-1", !qspState && "bg-green-700 text-white")}>
            {data?.[`${PROPOSED_CHANGES_OBJECT}Open`]?.count ?? "..."}
          </Badge>
        </>
      ),
      name: "open",
    },
    {
      label: (
        <>
          Closed
          <Badge className={classNames("ml-1", qspState && "bg-green-700 text-white")}>
            {data?.[`${PROPOSED_CHANGES_OBJECT}Close`]?.count ?? "..."}
          </Badge>
        </>
      ),
      name: "close",
    },
  ];

  return (
    <Content.Card>
      <Content.CardTitle
        title="Proposed changes"
        badgeContent={proposedChangesData?.count ?? "..."}
        reload={() => refetch()}
        isReloadLoading={loading}
        end={
          <ObjectHelpButton
            className="ml-auto"
            documentationUrl={schema?.documentation}
            kind={PROPOSED_CHANGES_OBJECT}
          />
        }
      />

      <div className="flex items-center m-2 gap-2">
        <SearchInput
          loading={loading}
          onChange={debouncedHandleSearch}
          placeholder="Search a Proposed Change"
          className="border-none focus-visible:ring-0 h-7"
          containerClassName=" grow"
          data-testid="proposed-changes-list-search-bar"
        />

        <TabsButtons tabs={tabs} qsp={QSP.PROPOSED_CHANGES_STATE} />

        <ButtonWithTooltip
          disabled={!permission.create.isAllowed}
          tooltipEnabled={!permission.create.isAllowed}
          tooltipContent={permission.create.message ?? undefined}
          onClick={() => navigate(constructPath("/proposed-changes/new"))}
          data-testid="add-proposed-changes-button"
        >
          <Icon icon="mdi:plus" className="text-sm" />
          New proposed change
        </ButtonWithTooltip>
      </div>

      <Table
        columns={columns}
        rows={rows}
        onDelete={(row) => setRelatedRowToDelete(row)}
        permission={permission}
        className="border-0 border-t"
      />

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
    </Content.Card>
  );
};
