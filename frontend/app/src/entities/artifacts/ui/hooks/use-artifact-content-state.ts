import type { ArtifactObject } from "@/entities/artifacts/domain/model/artifact";
import { isArtifactContentNotServed } from "@/entities/artifacts/domain/rules/is-artifact-content-not-served";
import { useGetArtifactFile } from "@/entities/artifacts/ui/queries/get-artifact-file.query";

interface ArtifactContentState {
  /** Whether the request for the content has ended, or there is no content to request. */
  isSettled: boolean;
  /** Whether the server answered that the file is missing or that it refuses to serve it. */
  isNotServed: boolean;
}

// Reads the query of the content view of the artifact, so it sends no second request.
export function useArtifactContentState(artifact: ArtifactObject): ArtifactContentState {
  const storageId = artifact.storage_id.value;
  const { isLoading, error } = useGetArtifactFile(
    { storageId: storageId ?? "", contentType: artifact.content_type.value },
    { enabled: Boolean(storageId) }
  );

  return { isSettled: !isLoading, isNotServed: isArtifactContentNotServed(error) };
}
