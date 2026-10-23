// PROTOTYPE design-jam commits-tab-pending-badge
import { formatNumberDisplay } from "@/shared/utils/number";

export const BASE_PATH = "/_proto/commits-tab-pending-badge";

export type PendingMeaning = "import" | "rebase";

export type CommitStateLabel =
  | "Remote head"
  | "Imported"
  | "Pending import"
  | "Not on this branch"
  | "Not on current history";

export interface MockCommit {
  hash: string;
  message: string;
  author: string;
  minutesAgo: number;
  states: CommitStateLabel[];
}

export interface Scenario {
  id: number;
  situation: string;
  condition: "BEHIND" | "IN_SYNC" | "REWRITTEN" | "NOT_TRACKED" | "LOADING";
  count: number | null;
  meaning: PendingMeaning;
  action: string;
  rebaseNote: string | null;
  warning: string | null;
  emptyState: { title: string; message: string } | null;
  commits: MockCommit[];
  overflow?: boolean;
}

const REBASE_BEHIND =
  "This branch does not sync with Git. The default branch has newer commits. Rebase the branch to use them.";
const REBASE_IN_SYNC =
  "This branch does not sync with Git. It uses the latest commit of the default branch.";

const HISTORY: MockCommit[] = [
  {
    hash: "4103739",
    message: "Add BGP peer group transform for the edge routers",
    author: "Damien Garros",
    minutesAgo: 60 * 26,
    states: [],
  },
  {
    hash: "9be2c01",
    message: "Fix the interface description check for LAG members",
    author: "Pete Crocker",
    minutesAgo: 60 * 50,
    states: [],
  },
];

const synced = (count: number, pending: CommitStateLabel = "Pending import"): MockCommit[] => [
  {
    hash: "e7f31aa",
    message: "Generate the DC2 spine configuration from the new topology template",
    author: "Baptiste Lemaire",
    minutesAgo: 12,
    states: count > 0 ? ["Remote head", pending] : ["Remote head", "Imported"],
  },
  ...(count > 1
    ? [
        {
          hash: "51c0d9e",
          message: "Rename the loopback pool used by the leaf generator",
          author: "Wim Van Deun",
          minutesAgo: 95,
          states: [pending],
        },
      ]
    : []),
  ...(count > 2
    ? [
        {
          hash: "b24e8f6",
          message: "Bump the device-config artifact definition to version 3",
          author: "Fatih Acar",
          minutesAgo: 240,
          states: [pending],
        },
      ]
    : []),
  {
    ...(HISTORY[0] as MockCommit),
    states: count > 0 ? ["Imported"] : [],
  },
];

export const SCENARIOS: Scenario[] = [
  {
    id: 1,
    situation: "Read-write repository, branch syncs with Git, 3 commits not imported yet",
    condition: "BEHIND",
    count: 3,
    meaning: "import",
    action: "The next sync imports them.",
    rebaseNote: null,
    warning: null,
    emptyState: null,
    commits: synced(3),
  },
  {
    id: 2,
    situation: "Read-write repository, branch syncs with Git, nothing pending",
    condition: "IN_SYNC",
    count: 0,
    meaning: "import",
    action: "",
    rebaseNote: null,
    warning: null,
    emptyState: null,
    commits: [...synced(0), HISTORY[1] as MockCommit],
  },
  {
    id: 3,
    situation: "Branch does not sync with Git, the default branch has 2 newer commits",
    condition: "BEHIND",
    count: 2,
    meaning: "rebase",
    action: "Rebase the branch to use them.",
    rebaseNote: REBASE_BEHIND,
    warning: null,
    emptyState: null,
    commits: synced(2, "Not on this branch"),
  },
  {
    id: 4,
    situation: "Branch does not sync with Git, up to date with the default branch",
    condition: "IN_SYNC",
    count: 0,
    meaning: "rebase",
    action: "",
    rebaseNote: REBASE_IN_SYNC,
    warning: null,
    emptyState: null,
    commits: [...synced(0), HISTORY[1] as MockCommit],
  },
  {
    id: 5,
    situation: "Branch does not sync with Git, 1,284 commits behind the default branch",
    condition: "BEHIND",
    count: 1284,
    meaning: "rebase",
    action: "Rebase the branch to use them.",
    rebaseNote: REBASE_BEHIND,
    warning: null,
    emptyState: null,
    commits: synced(3, "Not on this branch"),
  },
  {
    id: 6,
    situation: "Branch does not sync with Git, default branch history rewritten (force push)",
    condition: "REWRITTEN",
    count: null,
    meaning: "rebase",
    action: "",
    rebaseNote: null,
    warning:
      "This branch does not sync with Git, and the commit it uses (4103739) is no longer in the history of the default branch, for example after a force push. Rebase the branch to use the latest commit of the default branch.",
    emptyState: null,
    commits: [
      { ...(synced(2)[0] as MockCommit), states: ["Remote head", "Not on this branch"] },
      { ...(synced(2)[1] as MockCommit), states: ["Not on this branch"] },
      { ...(HISTORY[1] as MockCommit), states: ["Not on this branch"] },
    ],
  },
  {
    id: 7,
    situation: "Read-only repository, 2 new commits on the remote, waiting for a manual import",
    condition: "BEHIND",
    count: 2,
    meaning: "import",
    action: "Start the import to use them.",
    rebaseNote: null,
    warning: null,
    emptyState: null,
    commits: synced(2),
  },
  {
    id: 8,
    situation: "Repository added on this branch (staging), 1 commit waiting for the next sync",
    condition: "BEHIND",
    count: 1,
    meaning: "import",
    action: "The next sync imports it.",
    rebaseNote: null,
    warning: null,
    emptyState: null,
    commits: synced(1),
  },
  {
    id: 9,
    situation: "No count: the branch tracks no remote ref (NOT_TRACKED)",
    condition: "NOT_TRACKED",
    count: null,
    meaning: "import",
    action: "",
    rebaseNote: null,
    warning: null,
    emptyState: { title: "No commit log", message: "This branch tracks no remote ref." },
    commits: [],
  },
  {
    id: 10,
    situation: "First load of the commit log in progress",
    condition: "LOADING",
    count: null,
    meaning: "import",
    action: "",
    rebaseNote: null,
    warning: null,
    emptyState: null,
    commits: [],
  },
  {
    id: 11,
    situation:
      "Overflow: tab bar limited to 900px with long tab names, Commits partly scrolled away (data of scenario 3)",
    condition: "BEHIND",
    count: 2,
    meaning: "rebase",
    action: "Rebase the branch to use them.",
    rebaseNote: REBASE_BEHIND,
    warning: null,
    emptyState: null,
    commits: synced(2, "Not on this branch"),
    overflow: true,
  },
];

export const SCENARIO_OPTIONS = [
  "all",
  "1 synced, 3 pending",
  "2 synced, in sync",
  "3 non-synced, 2 behind",
  "4 non-synced, up to date",
  "5 non-synced, 1,284 behind",
  "6 rewritten",
  "7 read-only, 2 pending",
  "8 staging, 1 pending",
  "9 not tracked",
  "10 loading",
  "11 overflow",
];

export const pickScenarios = (option: string): Scenario[] => {
  const id = Number.parseInt(option, 10);
  const one = SCENARIOS.find((s) => s.id === id);
  return one ? [one] : SCENARIOS;
};

export const pluralizeCommits = (count: number) =>
  `${formatNumberDisplay(count)} ${count === 1 ? "commit" : "commits"}`;

export const getMeaningLabel = (meaning: PendingMeaning) =>
  meaning === "rebase" ? "not on this branch" : "pending import";

export const getPendingSentence = ({ count, meaning }: Pick<Scenario, "count" | "meaning">) =>
  count ? `${pluralizeCommits(count)} ${getMeaningLabel(meaning)}` : null;
