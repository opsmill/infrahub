import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ARTIFACT_OBJECT } from "@/shared/config/constants";
import { useTitle } from "@/shared/hooks/useTitle";

import { ArtifactsDetails } from "@/entities/artifacts/ui/artifact-details";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const ArtifactDetailsPage = () => {
  useTitle("Artifact");
  const { artifactId } = useParams();
  const { schema: artifactSchema } = useSchema(ARTIFACT_OBJECT, { required: true });
  const { isPending, error, data: permission } = useGetObjectPermissions(ARTIFACT_OBJECT);

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return <ArtifactsDetails artifactSchema={artifactSchema} artifactId={artifactId as string} />;
};

export const Component = ArtifactDetailsPage;
