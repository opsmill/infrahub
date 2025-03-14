import { QSP } from "@/config/qsp";
import { useRunGeneratorMutation } from "@/entities/generators/domain/run-generator.mutation";
import { constructPath } from "@/shared/api/rest/fetch";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { PlayIcon } from "lucide-react";
import { Link } from "react-router";
import { toast } from "react-toastify";

export interface GeneratorRunButtonProps extends ButtonProps {
  generatorId: string;
  targetNodeIds?: string[];
}

export function GeneratorRunButton({
  generatorId,
  targetNodeIds,
  children,
  ...props
}: GeneratorRunButtonProps) {
  const { isPending, mutate } = useRunGeneratorMutation();

  const handleRunGenerator = () => {
    mutate(
      { generatorId, targetNodeIds },
      {
        onSuccess: ({ taskId }) => {
          const url = constructPath(window.location.pathname, [
            { name: QSP.TAB, value: "tasks" },
            { name: QSP.TASK_ID, value: taskId },
          ]);

          toast(
            <Alert
              type={ALERT_TYPES.SUCCESS}
              message={
                <>
                  Generator started successfully.
                  <br />
                  <Link to={url} className="underline flex items-center gap-1">
                    View task details
                  </Link>
                </>
              }
            />
          );
        },
      }
    );
  };

  return (
    <Button
      isLoading={isPending}
      disabled={isPending}
      variant="active"
      onClick={handleRunGenerator}
      {...props}
    >
      {!isPending && <PlayIcon className="size-4 mr-2" />}
      {children ?? "Run"}
    </Button>
  );
}
