import type { GraphQLResult } from "@/shared/api/graphql/types";

import type { RepositoryCommitsResponse } from "@/entities/repository/api/get-repository-commits-from-api";
import type {
  RepositoryCommit,
  RepositoryCommitState,
} from "@/entities/repository/domain/model/repository";

export type RepositoryCommitsWire = RepositoryCommitsResponse["InfrahubRepositoryCommits"];

type RepositoryCommitNodeWire = RepositoryCommitsWire["edges"][number]["node"];

export const generateCommitsApiResult = (
  response: RepositoryCommitsWire
): GraphQLResult<RepositoryCommitsResponse> => ({ data: { InfrahubRepositoryCommits: response } });

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

export const generateRepositoryCommit = (
  overrides: Partial<RepositoryCommit> = {}
): RepositoryCommit => {
  const { authored_at, ...commit } = generateRepositoryCommitNode(overrides);
  return { ...commit, authored_at: String(authored_at) };
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

export const generateOrphanedCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "ORPHANED",
    imported_commit: fullHash(BEHIND_IMPORTED),
    remote_head: fullHash(BEHIND_HEAD),
    edges: [{ node: node(BEHIND_HEAD, "HEAD", "Bump firmware baseline", "Grace Hopper") }],
  });

export const PAGE_ONE_HEAD = "a000001";
export const PAGE_ONE_LAST = "a000020";
export const PAGE_TWO_FIRST = "b000001";

export const generateFirstCommitsPage = () =>
  generateRepositoryCommitsResponse({
    condition: "IN_SYNC",
    imported_commit: fullHash(PAGE_ONE_HEAD),
    remote_head: fullHash(PAGE_ONE_HEAD),
    edges: Array.from({ length: 20 }, (_, index) => {
      const position = String(index + 1).padStart(6, "0");
      return {
        node: node(
          `a${position}`,
          index === 0 ? "HEAD" : "HISTORY",
          `Page one commit ${index + 1}`,
          "Ada Lovelace"
        ),
      };
    }),
  });

export const generateSecondCommitsPage = () =>
  generateRepositoryCommitsResponse({
    condition: "IN_SYNC",
    imported_commit: fullHash(PAGE_ONE_HEAD),
    remote_head: fullHash(PAGE_ONE_HEAD),
    edges: [
      { node: node(PAGE_ONE_LAST, "HISTORY", "Page one commit 20", "Ada Lovelace") },
      { node: node(PAGE_TWO_FIRST, "HISTORY", "Page two commit 1", "Linus Torvalds") },
    ],
  });

export const NOT_CLONED_MESSAGE = "No worker holds a copy of this repository yet.";

export const generateNotClonedCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "UNAVAILABLE",
    fetched_at: null,
    unavailable: { reason: "NOT_CLONED", message: NOT_CLONED_MESSAGE },
  });

export const NOT_IMPLEMENTED_MESSAGE = "Reading commits is not implemented on this deployment.";

export const generateNotImplementedCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "UNAVAILABLE",
    fetched_at: null,
    unavailable: { reason: "NOT_IMPLEMENTED", message: NOT_IMPLEMENTED_MESSAGE },
  });

export const JUST_CHECKED_AT = "2025-03-11T08:30:00Z";

export const generateJustCheckedCommitsResponse = () =>
  generateRepositoryCommitsResponse({
    condition: "IN_SYNC",
    imported_commit: fullHash(IN_SYNC_HEAD),
    remote_head: fullHash(IN_SYNC_HEAD),
    fetched_at: JUST_CHECKED_AT,
    checked_at: JUST_CHECKED_AT,
    edges: [{ node: node(IN_SYNC_HEAD, "HEAD", "Add device inventory", "Ada Lovelace") }],
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
