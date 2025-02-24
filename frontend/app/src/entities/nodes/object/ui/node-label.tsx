import { NODE_OBJECT } from "@/config/constants";
import { TextDisplay } from "@/shared/components/display/text-display";
import { Skeleton } from "@/shared/components/skeleton";
import { classNames } from "@/shared/utils/common";
import { useNodeLabel } from "../api/get-display-label.query";

type NodeLabelProps = {
  id?: string;
  kind?: string;
  maxChar?: number;
  className?: string;
};

export const NodeLabel = ({ id, kind = NODE_OBJECT, maxChar, className }: NodeLabelProps) => {
  const { isLoading, error, data } = useNodeLabel({ objectid: id, kind, enabled: !!id });

  if (isLoading) {
    return <Skeleton className="h-3 w-14" />;
  }

  if (!id) {
    return <div className="italic">Name id provided</div>;
  }

  if (error || !data?.display_label) {
    return (
      <div className="italic">
        <TextDisplay maxChars={maxChar} preventShowMore>
          {id}
        </TextDisplay>
      </div>
    );
  }

  return (
    <div className={classNames(className)}>
      <TextDisplay maxChars={maxChar} preventShowMore>
        {data?.display_label}
      </TextDisplay>
    </div>
  );
};
