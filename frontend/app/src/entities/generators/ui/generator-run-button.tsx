import { Button, type ButtonProps } from "@infrahub/ui";
import { PlayIcon } from "lucide-react";
import type React from "react";
import { Link, useParams } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { useRunGeneratorMutation } from "@/entities/generators/ui/queries/run-generator.mutation";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";

export interface GeneratorRunButtonProps extends ButtonProps {
  generatorId: string;
  targetNodeIds?: string[];
  children?: React.ReactNode;
}

export function GeneratorRunButton({
  generatorId,
  targetNodeIds,
  children,
  variant = "active",
  ...props
}: GeneratorRunButtonProps) {
  const { isPending, mutate } = useRunGeneratorMutation();
  const { objectKind, objectId } = useParams<{ objectKind: string; objectId: string }>();

  const handleRunGenerator = () => {
    mutate(
      { generatorId, targetNodeIds },
      {
        onSuccess: ({ taskId }) => {
          const url =
            objectKind && objectId
              ? getObjectDetailsUrl(objectKind, objectId, undefined, `tasks/${taskId}`)
              : constructPath(`/tasks/${taskId}`);

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
      isPending={isPending}
      isDisabled={isPending}
      variant={variant}
      onPress={handleRunGenerator}
      {...props}
    >
      {!isPending && <PlayIcon className="size-4" />}
      {children ?? "Run"}
    </Button>
  );
}
