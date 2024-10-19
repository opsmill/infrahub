import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Table, tRow } from "@/components/table/table";
import { Badge } from "@/components/ui/badge";
import useQuery, { useMutation } from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import { Icon } from "@iconify-icon/react";

import { TabsButtons } from "@/components/buttons/tabs-buttons";
import { ObjectHelpButton } from "@/components/menu/object-help-button";
import ModalDelete from "@/components/modals/modal-delete";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { CardWithBorder } from "@/components/ui/card";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { ARTIFACT_OBJECT, PROPOSED_CHANGES_OBJECT, TASK_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { DELETE_PROPOSED_CHANGE } from "@/graphql/mutations/proposed-changes/deleteProposedChange";
import { GET_PROPOSED_CHANGES } from "@/graphql/queries/proposed-changes/getProposedChanges";
import { getProposedChangesArtifacts } from "@/graphql/queries/proposed-changes/getProposedChangesArtifacts";
import { getProposedChangesTasks } from "@/graphql/queries/proposed-changes/getProposedChangesTasks";
import { useSchema } from "@/hooks/useSchema";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { ProposedChangesCounter } from "@/screens/proposed-changes/counter";
import { ProposedChangeDiffSummary } from "@/screens/proposed-changes/diff-summary";
import { ProposedChangesInfo } from "@/screens/proposed-changes/item-info";
import { ProposedChangesReviewers } from "@/screens/proposed-changes/reviewers";
import { classNames, debounce } from "@/utils/common";
import { constructPath } from "@/utils/fetch";
import { NetworkStatus } from "@apollo/client";
import { useState } from "react";
import { Link, LinkProps, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import UnauthorizedScreen from "../errors/unauthorized-screen";
import { getPermission } from "../permission/utils";

const STATES = {
  open: ["open"],
  close: ["closed", "merged", "canceled"],
};

export const ProposedChangesPage = () => {
  const navigate = useNavigate();
  const [qspState] = useQueryParam(QSP.PROPOSED_CHANGES_STATE, StringParam);
  useTitle("Proposed changes");
  const [search, setSearch] = useQueryParam(QSP.SEARCH, StringParam);
  const [relatedRowToDelete, setRelatedRowToDelete] = useState<tRow | undefined>();
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT);

  const [statesVisible, statesHidden] = qspState
    ? [STATES.close, STATES.open]
    : [STATES.open, STATES.close];

  const { loading, networkStatus, previousData, error, data, refetch } = useQuery(
    GET_PROPOSED_CHANGES,
    {
      variables: { statesVisible, statesHidden, search },
      notifyOnNetworkStatusChange: true,
    }
  );
  const [deleteProposedChange, { loading: isDeleteLoading }] = useMutation(DELETE_PROPOSED_CHANGE);

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
            {data?.[PROPOSED_CHANGES_OBJECT + (qspState ? "Hidden" : "Visible")]?.count ?? "..."}
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
            {data?.[PROPOSED_CHANGES_OBJECT + (qspState ? "Visible" : "Hidden")]?.count ?? "..."}
          </Badge>
        </>
      ),
      name: "close",
    },
  ];

  return (
    <>
      <Content.Title
        title={
          <h1 className="flex items-center gap-2">
            Proposed changes <Badge>{proposedChangesData?.count ?? "..."}</Badge>
          </h1>
        }
        reload={() => refetch()}
        isReloadLoading={loading}
      >
        <ObjectHelpButton
          className="ml-auto"
          documentationUrl={schema?.documentation}
          kind={PROPOSED_CHANGES_OBJECT}
        />
      </Content.Title>

      <Content>
        <CardWithBorder className="m-2">
          <div className="flex items-center m-2 gap-2">
            <SearchInput
              loading={loading}
              onChange={debouncedHandleSearch}
              placeholder="Search a Proposed Change"
              className="border-none focus-visible:ring-0 h-7"
              containerClassName=" flex-grow"
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
