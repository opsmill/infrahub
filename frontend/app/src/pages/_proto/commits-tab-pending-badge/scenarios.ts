// PROTOTYPE design-jam commits-tab-pending-badge
import { formatNumberDisplay } from "@/shared/utils/number";

export const BASE_PATH = "/_proto/commits-tab-pending-badge";

export type PendingMeaning = "import" | "rebase";

type Condition =
  | "BEHIND"
  | "IN_SYNC"
  | "REWRITTEN"
  | "ORPHANED"
  | "NO_REMOTE"
  | "NOT_TRACKED"
  | "REF_MISSING"
  | "LOADING"
  | "UNAVAILABLE"
  | "FAILED";

export type CommitStateLabel =
  | "Remote head"
  | "Imported"
  | "Pending import"
  | "Pending import on main"
  | "Behind"
  | "Not on current history";

export interface MockCommit {
  hash: string;
  message: string;
  author: string;
  minutesAgo: number;
  states: CommitStateLabel[];
}

interface ScenarioWarning {
  label: string;
  hint: string;
  message: string;
}

export interface Scenario {
  id: string;
  group: string;
  situation: string;
  condition: Condition;
  count: number | null;
  meaning: PendingMeaning;
  action: string;
  rebaseNote: string | null;
  warning: ScenarioWarning | null;
  emptyState: { title: string; message: string } | null;
  error: string | null;
  commits: MockCommit[];
  overflow?: boolean;
  split?: { behind: number; pendingOnMain: number; commits: MockCommit[] };
}

export const GROUPS = [
  { id: "A", title: "Read-write repository, branch syncs with Git" },
  { id: "B", title: "Read-write repository, branch does not sync with Git" },
  { id: "C", title: "Repository added on this branch (staging)" },
  { id: "D", title: "Read-only repository" },
  { id: "E", title: "No answer from the commit log" },
  { id: "F", title: "Layout" },
];

export const TRACKED_REF = "main";

const REBASE_BEHIND = "behind";
const REBASE_IN_SYNC = `This branch does not sync with Git and is up to date with ${TRACKED_REF}.`;

const IMPORT_NEXT_SYNC = "The next sync imports them.";
const IMPORT_MANUAL = "Start the import to use them.";
const REBASE_ACTION = "Rebase the branch to use them.";

const NEW_COMMITS: Omit<MockCommit, "states">[] = [
  {
    hash: "e7f31aa",
    message: "Generate the DC2 spine configuration from the new topology template",
    author: "Baptiste Lemaire",
    minutesAgo: 12,
  },
  {
    hash: "51c0d9e",
    message: "Rename the loopback pool used by the leaf generator",
    author: "Wim Van Deun",
    minutesAgo: 95,
  },
  {
    hash: "b24e8f6",
    message: "Bump the device-config artifact definition to version 3",
    author: "Fatih Acar",
    minutesAgo: 240,
  },
];

const IMPORTED_COMMIT: Omit<MockCommit, "states"> = {
  hash: "4103739",
  message: "Add BGP peer group transform for the edge routers",
  author: "Damien Garros",
  minutesAgo: 60 * 26,
};

const OLDER_COMMIT: Omit<MockCommit, "states"> = {
  hash: "9be2c01",
  message: "Fix the interface description check for LAG members",
  author: "Pete Crocker",
  minutesAgo: 60 * 50,
};

const newCommit = (index: number, states: CommitStateLabel[]): MockCommit => ({
  ...(NEW_COMMITS[index] as Omit<MockCommit, "states">),
  states,
});

const behindRows = (count: number, state: CommitStateLabel): MockCommit[] => [
  ...NEW_COMMITS.slice(0, Math.min(count, 3)).map((_, index) =>
    newCommit(index, index === 0 ? ["Remote head", state] : [state])
  ),
  { ...IMPORTED_COMMIT, states: ["Imported"] },
];

const inSyncRows: MockCommit[] = [
  newCommit(0, ["Remote head", "Imported"]),
  { ...IMPORTED_COMMIT, states: [] },
  { ...OLDER_COMMIT, states: [] },
];

const base = {
  count: null,
  meaning: "import" as PendingMeaning,
  action: "",
  rebaseNote: null,
  warning: null,
  emptyState: null,
  error: null,
  commits: [],
};

const A1: Scenario = {
  ...base,
  id: "A1",
  group: "A",
  situation: "3 commits pending import",
  condition: "BEHIND",
  count: 3,
  action: IMPORT_NEXT_SYNC,
  commits: behindRows(3, "Pending import"),
};

const A3: Scenario = { ...A1, id: "A3", situation: "1,284 commits pending import", count: 1284 };

const B1: Scenario = {
  ...base,
  id: "B1",
  group: "B",
  situation: "2 commits behind main",
  condition: "BEHIND",
  count: 2,
  meaning: "rebase",
  action: REBASE_ACTION,
  rebaseNote: REBASE_BEHIND,
  commits: behindRows(2, "Behind"),
};

export const SCENARIOS: Scenario[] = [
  A1,
  {
    ...base,
    id: "A2",
    group: "A",
    situation: "Nothing pending",
    condition: "IN_SYNC",
    count: 0,
    commits: inSyncRows,
  },
  A3,
  {
    ...base,
    id: "A4",
    group: "A",
    situation: "Remote branch history rewritten (REWRITTEN, no count)",
    condition: "REWRITTEN",
    warning: {
      label: "history rewritten",
      hint: "The remote branch history was rewritten, so nothing is reported as pending import.",
      message:
        "The tracked ref was rewritten. The imported commit is no longer part of its history, so nothing is reported as pending.",
    },
    commits: [newCommit(0, ["Remote head"]), newCommit(1, []), { ...OLDER_COMMIT, states: [] }],
  },
  {
    ...base,
    id: "A5",
    group: "A",
    situation: "Imported commit missing from the remote (ORPHANED, no count)",
    condition: "ORPHANED",
    warning: {
      label: "imported commit missing",
      hint: "The imported commit could not be found on the remote.",
      message: "The imported commit could not be found on the remote.",
    },
    commits: [newCommit(0, ["Remote head"]), { ...OLDER_COMMIT, states: [] }],
  },
  {
    ...base,
    id: "A6",
    group: "A",
    situation: "No remote branch with this name (NO_REMOTE, no count)",
    condition: "NO_REMOTE",
    emptyState: { title: "No commit log", message: "The tracked ref has no remote counterpart." },
  },
  B1,
  {
    ...base,
    id: "B2",
    group: "B",
    situation: "Up to date with main",
    condition: "IN_SYNC",
    count: 0,
    meaning: "rebase",
    rebaseNote: REBASE_IN_SYNC,
    commits: inSyncRows,
  },
  {
    ...B1,
    id: "B3",
    situation: "1,284 commits behind main",
    count: 1284,
    commits: behindRows(3, "Behind"),
  },
  {
    ...base,
    id: "B4",
    group: "B",
    situation: "Diverged from main: its history was rewritten (REWRITTEN, no count)",
    condition: "REWRITTEN",
    meaning: "rebase",
    warning: {
      label: "diverged",
      hint: "This branch has diverged from main. Rebase the branch to use the latest commit of main.",
      message:
        "This branch does not sync with Git and has diverged from main: the commit it uses (4103739) is no longer in the history of main, for example after a force push. Rebase the branch to use the latest commit of main.",
    },
    commits: [
      newCommit(0, ["Remote head", "Behind"]),
      newCommit(1, ["Behind"]),
      { ...OLDER_COMMIT, states: ["Behind"] },
    ],
  },
  {
    ...base,
    id: "B6",
    group: "B",
    situation: "No commit of its own on this branch (NOT_TRACKED, no count)",
    condition: "NOT_TRACKED",
    meaning: "rebase",
    emptyState: { title: "No commit log", message: "This branch tracks no remote ref." },
  },
  {
    ...base,
    id: "C1",
    group: "C",
    situation: "1 commit pending import, the next sync imports it",
    condition: "BEHIND",
    count: 1,
    action: "The next sync imports it.",
    commits: behindRows(1, "Pending import"),
  },
  {
    ...base,
    id: "C2",
    group: "C",
    situation: "Nothing pending",
    condition: "IN_SYNC",
    count: 0,
    commits: inSyncRows,
  },
  {
    ...base,
    id: "D1",
    group: "D",
    situation: "2 new commits waiting for a manual import",
    condition: "BEHIND",
    count: 2,
    action: IMPORT_MANUAL,
    commits: behindRows(2, "Pending import"),
  },
  {
    ...base,
    id: "D2",
    group: "D",
    situation: "Nothing pending",
    condition: "IN_SYNC",
    count: 0,
    commits: inSyncRows,
  },
  {
    ...base,
    id: "D3",
    group: "D",
    situation: "Tracked branch or tag deleted on the remote (REF_MISSING, no count)",
    condition: "REF_MISSING",
    warning: {
      label: "tracked ref missing",
      hint: "The tracked branch or tag no longer exists on the remote. The imported commit is still in use.",
      message:
        "The tracked ref no longer exists on the remote. The imported commit is still the one in use.",
    },
    commits: [
      { ...IMPORTED_COMMIT, states: ["Imported"] },
      { ...OLDER_COMMIT, states: [] },
    ],
  },
  { ...base, id: "E1", group: "E", situation: "First load in progress", condition: "LOADING" },
  {
    ...base,
    id: "E2",
    group: "E",
    situation: "No worker holds a copy yet (NOT_CLONED), retrying",
    condition: "UNAVAILABLE",
    emptyState: {
      title: "Commit log not available yet",
      message: "No worker holds a copy of this repository yet.",
    },
  },
  {
    ...base,
    id: "E3",
    group: "E",
    situation: "Request failed",
    condition: "FAILED",
    error: "Failed to fetch the commit log: the server did not respond.",
  },
  {
    ...B1,
    id: "F1",
    group: "F",
    situation: "Overflow: tab bar limited to 900px, Commits partly scrolled away (data of B1)",
    overflow: true,
  },
  {
    ...A3,
    id: "F2",
    group: "F",
    situation: "Overflow: tab bar limited to 900px, large pending number (data of A3)",
    overflow: true,
  },
];

export const SCENARIO_OPTIONS = [
  "all",
  ...SCENARIOS.map((scenario) => `${scenario.id} ${scenario.situation.split(/ \(|:/)[0]}`),
];

export const pickScenarios = (option: string): Scenario[] => {
  const one = SCENARIOS.find((scenario) => scenario.id === option.split(" ")[0]);
  return one ? [one] : SCENARIOS;
};

export const pluralizeCommits = (count: number) =>
  `${formatNumberDisplay(count)} ${count === 1 ? "commit" : "commits"}`;

export const getMeaningLabel = (meaning: PendingMeaning) =>
  meaning === "rebase" ? `behind ${TRACKED_REF}` : "pending import";

export const getPendingSentence = ({ count, meaning }: Pick<Scenario, "count" | "meaning">) =>
  count ? `${pluralizeCommits(count)} ${getMeaningLabel(meaning)}` : null;

export const getSplitSentences = ({ behind, pendingOnMain }: NonNullable<Scenario["split"]>) => ({
  behind: `${pluralizeCommits(behind)} behind ${TRACKED_REF}`,
  pendingOnMain: `${pluralizeCommits(pendingOnMain)} pending import on ${TRACKED_REF}`,
  action: `After ${TRACKED_REF} imports ${pendingOnMain === 1 ? "it" : "them"}, rebase the branch to use all ${formatNumberDisplay(behind + pendingOnMain)}.`,
});

export const getRebaseNote = (count: number) =>
  `This branch does not sync with Git and is behind ${TRACKED_REF} by ${pluralizeCommits(count)}. Rebase the branch to use them.`;
