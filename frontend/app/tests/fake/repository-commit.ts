import type {
  RepositoryCommitState,
  RepositoryGitCondition,
  RepositoryGitUnavailableReason,
} from "@/entities/repository/domain/model/repository";

export interface RepositoryCommitNodeWire {
  hash: string;
  short_hash: string;
  summary: string;
  author_name: string;
  authored_at: string;
  state: RepositoryCommitState;
}

export interface RepositoryCommitsWire {
  repository_id: string;
  branch_name: string;
  git_ref: string | null;
  condition: RepositoryGitCondition;
  imported_commit: string | null;
  remote_head: string | null;
  pending_count: number | null;
  fetched_at: string | null;
  checked_at: string | null;
  unavailable: { reason: RepositoryGitUnavailableReason; message: string } | null;
  edges: Array<{ node: RepositoryCommitNodeWire }>;
}

export const fullHash = (shortHash: string) => shortHash.padEnd(40, "0");

export const generateRepositoryCommitNode = (
  overrides: Partial<RepositoryCommitNodeWire> = {}
): RepositoryCommitNodeWire => {
  const shortHash = overrides.short_hash ?? "abc1234";
  return {
    hash: fullHash(shortHash),
    short_hash: shortHash,
    summary: "Add device inventory",
    author_name: "Ada Lovelace",
    authored_at: "2025-03-10T10:00:00Z",
    state: "HISTORY",
    ...overrides,
  };
};

export const generateRepositoryCommitsResponse = (
  overrides: Partial<RepositoryCommitsWire> = {}
): RepositoryCommitsWire => ({
  repository_id: "repo-1",
  branch_name: "test-branch",
  git_ref: "main",
  condition: "IN_SYNC",
  imported_commit: null,
  remote_head: null,
  pending_count: null,
  fetched_at: "2025-03-10T12:00:00Z",
  checked_at: null,
  unavailable: null,
  edges: [],
  ...overrides,
});

const node = (
  short_hash: string,
  state: RepositoryCommitState,
  summary: string,
  author_name: string
) => generateRepositoryCommitNode({ short_hash, state, summary, author_name });

export const BEHIND_HEAD = "f1e2d3c";
export const BEHIND_IMPORTED = "d4e5f6a";

export const generateBehindCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "BEHIND",
    imported_commit: fullHash(BEHIND_IMPORTED),
    remote_head: fullHash(BEHIND_HEAD),
    pending_count: 2,
    edges: [
      { node: node(BEHIND_HEAD, "HEAD", "Bump firmware baseline", "Grace Hopper") },
      { node: node("b2c3d4e", "PENDING", "Add site Paris", "Ada Lovelace") },
      { node: node("9a8b7c6", "HISTORY", "Merge branch feature/vlans", "Linus Torvalds") },
      { node: node("c3d4e5f", "PENDING", "Rename core switches", "Grace Hopper") },
      { node: node(BEHIND_IMPORTED, "IMPORTED", "Add device inventory", "Ada Lovelace") },
      { node: node("e5f6a7b", "HISTORY", "Initial import", "Linus Torvalds") },
    ],
  });

export const IN_SYNC_HEAD = "a1b2c3d";

export const generateInSyncCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "IN_SYNC",
    imported_commit: fullHash(IN_SYNC_HEAD),
    remote_head: fullHash(IN_SYNC_HEAD),
    edges: [
      { node: node(IN_SYNC_HEAD, "HEAD", "Add device inventory", "Ada Lovelace") },
      { node: node("e5f6a7b", "HISTORY", "Initial import", "Linus Torvalds") },
    ],
  });

export const generateRewrittenCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "REWRITTEN",
    imported_commit: fullHash(BEHIND_IMPORTED),
    remote_head: fullHash("0a1b2c3"),
    pending_count: null,
    edges: [
      { node: node("0a1b2c3", "HEAD", "Squash everything", "Grace Hopper") },
      { node: node("1b2c3d4", "UNRELATED", "Rewrite history", "Grace Hopper") },
      { node: node("2c3d4e5", "UNRELATED", "Start over", "Grace Hopper") },
    ],
  });

export const NOT_CLONED_MESSAGE = "No worker holds a copy of this repository yet.";

export const generateNotClonedCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "UNAVAILABLE",
    fetched_at: null,
    unavailable: { reason: "NOT_CLONED", message: NOT_CLONED_MESSAGE },
  });

export const READ_ONLY_FETCHED_AT = "2025-03-10T12:00:00Z";
export const READ_ONLY_CHECKED_AT = "2025-03-11T08:30:00Z";

export const generateReadOnlyCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    git_ref: "v1.2.0",
    condition: "BEHIND",
    imported_commit: fullHash(BEHIND_IMPORTED),
    remote_head: fullHash(BEHIND_HEAD),
    pending_count: 1,
    fetched_at: READ_ONLY_FETCHED_AT,
    checked_at: READ_ONLY_CHECKED_AT,
    edges: [
      { node: node(BEHIND_HEAD, "HEAD", "Bump firmware baseline", "Grace Hopper") },
      { node: node(BEHIND_IMPORTED, "IMPORTED", "Add device inventory", "Ada Lovelace") },
    ],
  });
