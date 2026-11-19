export class ArtifactFileError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ArtifactFileError";
    this.status = status;
  }
}
