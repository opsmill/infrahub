import {
  COMMIT_HASH,
  GITHUB_HOST,
  getGitHubRepositoryPath,
} from "@/entities/repository/domain/rules/get-commit-web-url";

export function getCompareWebUrl(location: string, base: string, head: string): string | null {
  if (!COMMIT_HASH.test(base) || !COMMIT_HASH.test(head)) return null;
  const repositoryPath = getGitHubRepositoryPath(location);
  if (!repositoryPath) return null;
  return `https://${GITHUB_HOST}/${repositoryPath}/compare/${base}...${head}`;
}
