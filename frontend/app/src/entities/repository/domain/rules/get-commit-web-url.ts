const GITHUB_HOST = "github.com";
const SCP_PREFIX = `git@${GITHUB_HOST}:`;
const PATH_SEGMENT = /^[A-Za-z0-9._-]+$/;
const COMMIT_HASH = /^[0-9a-f]{7,64}$/i;

function parseRemote(location: string): URL | null {
  const httpsLike = location.startsWith(SCP_PREFIX)
    ? `https://${GITHUB_HOST}/${location.slice(SCP_PREFIX.length)}`
    : location.replace(/^ssh:\/\//, "https://");
  try {
    return new URL(httpsLike);
  } catch {
    return null;
  }
}

function getGitHubRepositoryPath(location: string): string | null {
  const url = parseRemote(location.trim());
  if (!url || url.hostname !== GITHUB_HOST || url.port || url.search || url.hash) return null;
  if (url.protocol !== "https:" && url.protocol !== "http:") return null;

  const segments = url.pathname
    .replace(/^\/+|\/+$/g, "")
    .replace(/\.git$/, "")
    .split("/");
  if (segments.length !== 2 || !segments.every((segment) => PATH_SEGMENT.test(segment))) {
    return null;
  }
  return segments.join("/");
}

export function getCommitWebUrl(location: string, hash: string): string | null {
  if (!COMMIT_HASH.test(hash)) return null;
  const repositoryPath = getGitHubRepositoryPath(location);
  if (!repositoryPath) return null;
  return `https://${GITHUB_HOST}/${repositoryPath}/commit/${hash}`;
}
