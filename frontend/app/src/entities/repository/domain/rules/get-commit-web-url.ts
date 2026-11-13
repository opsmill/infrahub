const GITHUB_HOST = "github.com";
const SCP_PREFIX = `git@${GITHUB_HOST}:`;
const PATH_SEGMENT = /^[A-Za-z0-9._-]+$/;
const COMMIT_HASH = /^[0-9a-f]{7,64}$/i;

const SSH_SCHEME = "ssh://";
const SSH_DEFAULT_PORT = "22";

function toUrl(location: string): URL | null {
  try {
    return new URL(location);
  } catch {
    return null;
  }
}

function parseRemote(location: string): URL | null {
  if (location.startsWith(SCP_PREFIX)) {
    return toUrl(`https://${GITHUB_HOST}/${location.slice(SCP_PREFIX.length)}`);
  }
  if (!location.startsWith(SSH_SCHEME)) return toUrl(location);

  const url = toUrl(`https://${location.slice(SSH_SCHEME.length)}`);
  if (url?.port === SSH_DEFAULT_PORT) url.port = "";
  return url;
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
