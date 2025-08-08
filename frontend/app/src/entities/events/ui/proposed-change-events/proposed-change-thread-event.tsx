import { useGetProposedChangeThread } from "@/entities/proposed-changes/domain/get-proposed-change-thread.query";
import { Thread } from "@/shared/components/conversations/thread";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

export const ProposedChangeThreadEvent = ({ id }: { id: string }) => {
  const { data, isPending, error } = useGetProposedChangeThread({ threadId: id });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occured while fetching thread conversation." />;
  }

  if (!data) {
    return <NoDataFound message="No conversation found for this thread." />;
  }

  return <Thread thread={data} />;
};
