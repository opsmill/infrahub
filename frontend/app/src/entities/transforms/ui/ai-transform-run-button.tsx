import { PlayIcon } from "lucide-react";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button, type ButtonProps } from "@/shared/components/ui/button";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useTriggerAITransformMutation } from "@/entities/transforms/ui/queries/trigger-ai-transform.mutation";

type AITransformRunButtonProps = {
  transformId: string;
  size?: ButtonProps["size"];
  variant?: ButtonProps["variant"];
};

export const AITransformRunButton = (props: AITransformRunButtonProps) => {
  const { transformId, size, variant = "active" } = props;
  const { isPending, mutate } = useTriggerAITransformMutation();
  const { isAuthenticated } = useAuth();

  const handleRun = () => {
    if (!isAuthenticated || isPending) return;
    mutate(
      { transformId },
      {
        onSuccess: () => {
          toast(<Alert message="AI report triggered" type={ALERT_TYPES.SUCCESS} />);
        },
        onError: (error) => {
          console.error("Error triggering AI transform:", error);
          toast(
            <Alert
              message="An error occurred while triggering the AI report"
              type={ALERT_TYPES.ERROR}
            />
          );
        },
      }
    );
  };

  return (
    <Button
      variant={variant}
      size={size}
      disabled={!isAuthenticated || isPending}
      onClick={handleRun}
    >
      <PlayIcon className={classNames("mr-2 size-4", isPending && "animate-spin")} />
      Run
    </Button>
  );
};
