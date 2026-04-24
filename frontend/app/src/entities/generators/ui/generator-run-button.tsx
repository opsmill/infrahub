import { PlayIcon } from "lucide-react";
import { Link } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button, type ButtonProps } from "@/shared/components/ui/button";
import { QSP } from "@/shared/config/qsp";

import { useRunGeneratorMutation } from "@/entities/generators/ui/queries/run-generator.mutation";

export interface GeneratorRunButtonProps extends ButtonProps {
  generatorId: string;
  targetNodeIds?: string[];
}

export function GeneratorRunButton({
  generatorId,
  targetNodeIds,
  children,
  variant = "active",
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
                  <Link to={url} className="flex items-center gap-1 underline">
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
      variant={variant}
      onClick={handleRunGenerator}
      {...props}
    >
      {!isPending && <PlayIcon className="mr-2 size-4" />}
      {children ?? "Run"}
    </Button>
  );
}
