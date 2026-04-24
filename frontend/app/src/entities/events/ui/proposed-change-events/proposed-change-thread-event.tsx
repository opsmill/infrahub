import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { Thread } from "@/entities/proposed-changes/ui/conversations/thread";
import { useGetProposedChangeThread } from "@/entities/proposed-changes/ui/queries/get-proposed-change-thread.query";

interface ProposedChangeThreadEventProps {
  id: string;
}

export const ProposedChangeThreadEvent = ({ id }: ProposedChangeThreadEventProps) => {
  const { data, isPending, error } = useGetProposedChangeThread({ threadId: id });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message="An error occurred while fetching thread conversation." />;
  }

  if (!data) {
    return <NoDataFound message="No conversation found for this thread." />;
  }

  return <Thread thread={data} displayContext />;
};
