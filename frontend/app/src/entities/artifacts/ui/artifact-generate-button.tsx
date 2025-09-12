import { RefreshCwIcon } from "lucide-react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { useGenerateArtifactMutation } from "@/entities/artifacts/domain/generate-artifact.mutation";
import { useAuth } from "@/entities/authentication/ui/useAuth";

type ArtifactGenerateButtonProps = {
  label?: string;
  artifactId?: string;
  artifactDefinitionId: string;
};

export const ArtifactGenerateButton = (props: ArtifactGenerateButtonProps) => {
  const { label, artifactId, artifactDefinitionId } = props;
  const { isPending, mutate } = useGenerateArtifactMutation();

  const { isAuthenticated } = useAuth();

  const handleGenerate = () => {
    if (!isAuthenticated || isPending) return;
    mutate(
      {
        artifactDefinitionId,
        ...(artifactId ? { nodeIds: [artifactId] } : {}),
      },
      {
        onSuccess: async () => {
          await queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes("is-task-running"),
          });

          toast(
            <Alert
              message={artifactId ? "Artifact re-generated" : "Artifacts generated"}
              type={ALERT_TYPES.SUCCESS}
            />
          );
        },
        onError: (error) => {
          console.error("Error when generating artifacts: ", error);

          toast(
            <Alert
              message={
                artifactId
                  ? "An error occurred while re-generating the artifact"
                  : "An error occurred while generating artifacts"
              }
              type={ALERT_TYPES.ERROR}
            />
          );
        },
      }
    );
  };

  return (
    <Button variant="active" disabled={!isAuthenticated || isPending} onClick={handleGenerate}>
      <RefreshCwIcon className={classNames("mr-2 size-4", isPending && "animate-spin")} />
      {label ?? "Generate"}
    </Button>
  );
};
