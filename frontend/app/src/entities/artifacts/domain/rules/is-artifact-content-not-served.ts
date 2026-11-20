import { ArtifactFileError } from "@/entities/artifacts/domain/model/artifact-file-error";

const HTTP_NOT_FOUND = 404;
const HTTP_CONFLICT = 409;

/**
 * Whether the server answered about the stored file that it is not there (404) or that it refuses
 * to serve it because it failed its integrity check (409). Other failures say nothing about the file.
 */
export function isArtifactContentNotServed(error: unknown): boolean {
  return (
    error instanceof ArtifactFileError &&
    (error.status === HTTP_NOT_FOUND || error.status === HTTP_CONFLICT)
  );
}
