import { useGetProposedChangeThread } from "@/entities/proposed-changes/domain/get-proposed-change-thread.query";
import { Thread } from "@/shared/components/conversations/thread";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

export const ProposedChangeThreadEvent = ({ id }: { id: string }) => {
  const { data, isPending } = useGetProposedChangeThread({ threadId: id });

  if (isPending) {
    return <LoadingIndicator />;
  }

  return <Thread thread={data} />;
};
