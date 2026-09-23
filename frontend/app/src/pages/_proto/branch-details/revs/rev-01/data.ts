// PROTOTYPE — throwaway, delete with the /_proto route. Mocked worst-case data.

export type GitState = "in-sync" | "import-error" | "syncing" | "unknown";
export type RunState = "failed" | "running" | "passed";

// Colours mirror the CoreRepository.sync_status dropdown values used by the IFC-3200 canvas.
export const GIT_STATE: Record<GitState, { label: string; color: string }> = {
  "in-sync": { label: "In Sync", color: "#60a5fa" },
  "import-error": { label: "Import Error", color: "#f87171" },
  syncing: { label: "Syncing", color: "#fcd34d" },
  unknown: { label: "Unknown", color: "#d6d3d1" },
};

export type ImportError = {
  title: string;
  detail: (string | { code: string })[];
  taskId: string;
};

export type GeneratorRun = {
  definition: string;
  state: RunState;
  targets: number;
  failedTargets?: number;
  message?: string;
  taskId: string;
  updatedAt: string;
};

export type Repo = {
  id: string;
  name: string;
  readOnly: boolean;
  gitState: GitState;
  commit: string;
  upstream?: string;
  behind?: number;
  lastImport?: string;
  importError?: ImportError;
  generators: GeneratorRun[];
};

export type ArtifactsSummary = {
  state: RunState;
  failed: number;
  running: number;
  total: number;
  taskId: string;
  message?: string;
};

export type BranchMock = {
  name: string;
  description: string;
  syncWithGit: boolean;
  schemaDiffers: boolean;
  lastRebase: string;
};

export type BranchTask = {
  id: string;
  title: string;
  state: "COMPLETED" | "FAILED";
  updatedAt: string;
};

export type Scenario =
  | "incident"
  | "import-error"
  | "generator-failed"
  | "running"
  | "many-errors"
  | "tasks-unknown"
  | "all-clear"
  | "no-repos"
  | "loading"
  | "denied";

export const SCENARIOS: { id: Scenario; label: string }[] = [
  { id: "incident", label: "Import error + failed generator" },
  { id: "import-error", label: "Import error only (blocked)" },
  { id: "generator-failed", label: "Failed generator only (warn)" },
  { id: "running", label: "Import and generators running" },
  { id: "many-errors", label: "5 import errors, 40 repos" },
  { id: "tasks-unknown", label: "Task query failed" },
  { id: "all-clear", label: "Everything passed" },
  { id: "no-repos", label: "No Git counterpart" },
  { id: "loading", label: "Loading" },
  { id: "denied", label: "No permission on repositories" },
];

export type TaskState = "COMPLETED" | "FAILED" | "RUNNING";

export type TaskLog = { severity: "info" | "warning" | "error"; message: string; at: string };

export type TaskRow = {
  id: string;
  title: string;
  state: TaskState;
  workflow: "Import" | "Generator" | "Artifacts" | "Validate" | "Rebase";
  related: string;
  updatedAt: string;
  logs: TaskLog[];
};

export type ProtoData = {
  branch: BranchMock;
  status: "ok" | "loading" | "denied";
  repos: Repo[];
  artifacts: ArtifactsSummary | null;
  tasksUnknown: boolean;
  unplacedGenerators: number;
  branchTasks: BranchTask[];
  tasks: TaskRow[];
};

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

const ok = (definition: string, targets: number, minutes: number): GeneratorRun => ({
  definition,
  state: "passed",
  targets,
  taskId: `task-${definition}`,
  updatedAt: ago(minutes),
});

const IMPORT_ERRORS: ImportError[] = [
  {
    title: "schema file not found",
    detail: [
      { code: ".infrahub.yml" },
      " declares ",
      { code: "schemas/site_fra1.yml" },
      ", which does not exist at ",
      { code: "a19cd44" },
      ".",
    ],
    taskId: "task-import-1",
  },
  {
    title: "duplicate transformation name",
    detail: [
      "Two entries in ",
      { code: ".infrahub.yml" },
      " both define ",
      { code: "device_interfaces" },
      ".",
    ],
    taskId: "task-import-2",
  },
  {
    title: "invalid artifact definition",
    detail: [
      { code: "artifact_definitions[3].targets" },
      " refers to group ",
      { code: "edge_routers" },
      ", which doesn't exist.",
    ],
    taskId: "task-import-3",
  },
  {
    title: "schema validation failed",
    detail: [
      "Attribute ",
      { code: "InfraDevice.asn" },
      " changes kind from ",
      { code: "Number" },
      " to ",
      { code: "Text" },
      " without a migration.",
    ],
    taskId: "task-import-4",
  },
  {
    title: "Python transform failed to load",
    detail: [
      { code: "transforms/interfaces.py" },
      ": ",
      { code: "ModuleNotFoundError: netutils" },
      ".",
    ],
    taskId: "task-import-5",
  },
];

const BASE: Repo[] = [
  {
    id: "r1",
    name: "network-automation-generators-emea-datacenter-fabric-templates",
    readOnly: false,
    gitState: "in-sync",
    commit: "7fa2e51",
    upstream: "7fa2e51",
    behind: 0,
    lastImport: ago(7),
    generators: [ok("dc-fabric-leaf-spine", 48, 6), ok("dc-fabric-underlay", 12, 6)],
  },
  {
    id: "r2",
    name: "infrastructure-templates",
    readOnly: false,
    gitState: "in-sync",
    commit: "8f3c2a1",
    upstream: "8f3c2a1",
    behind: 0,
    lastImport: ago(6),
    generators: [],
  },
  {
    id: "r3",
    name: "network-services",
    readOnly: false,
    gitState: "in-sync",
    commit: "61ba9c3",
    upstream: "61ba9c3",
    behind: 0,
    lastImport: ago(5),
    generators: [ok("edge-peering", 12, 5)],
  },
  {
    id: "r4",
    name: "vendor-golden-configs",
    readOnly: true,
    gitState: "in-sync",
    commit: "v2.4.1 · 77aa01b",
    upstream: "v2.4.1 · 77aa01b",
    behind: 0,
    lastImport: ago(40 * 24 * 60),
    generators: [],
  },
];

const filler = (n: number): Repo => {
  const sha = (0x1_a2_b3_c4 + n * 7919).toString(16).slice(0, 7);
  return {
    id: `f${n}`,
    name: `site-config-${String(n).padStart(2, "0")}`,
    readOnly: false,
    gitState: "in-sync",
    commit: sha,
    upstream: sha,
    behind: 0,
    lastImport: ago(8 + n),
    generators: n % 4 === 0 ? [ok(`site-${n}`, 3, 8 + n)] : [],
  };
};

const withImportError = (repo: Repo, error: ImportError, behind: number): Repo => ({
  ...repo,
  gitState: "import-error",
  upstream: "a19cd44",
  behind,
  importError: error,
});

const FAILED_GENERATOR: GeneratorRun = {
  definition: "dc-fabric-leaf-spine",
  state: "failed",
  targets: 48,
  failedTargets: 7,
  message: "KeyError: 'asn' in generators/fabric.py:118 (target leaf-ams1-r12-07)",
  taskId: "task-gen-failed",
  updatedAt: ago(4),
};

const BRANCH: BranchMock = {
  name: "ple-emea-fabric-expansion-ams1-phase-2-leaf-spine-upgrade",
  description: "Adds 12 leaf switches in AMS1 hall 3 and regenerates the fabric underlay.",
  syncWithGit: true,
  schemaDiffers: false,
  lastRebase: ago(2 * 24 * 60),
};

const BRANCH_TASKS: BranchTask[] = [
  { id: "bt-1", title: "Validate branch", state: "COMPLETED", updatedAt: ago(30) },
  { id: "bt-2", title: "Rebase branch", state: "COMPLETED", updatedAt: ago(2 * 24 * 60) },
];

export function buildData(scenario: Scenario, repoCount: number, hasUpstream: boolean): ProtoData {
  const pool = [...BASE];
  const wanted = scenario === "many-errors" ? 40 : Math.max(1, repoCount);
  for (let n = 1; pool.length < wanted; n++) pool.push(filler(n));
  let repos = pool.slice(0, wanted);

  let artifacts: ArtifactsSummary | null = {
    state: "passed",
    failed: 0,
    running: 0,
    total: 300,
    taskId: "task-artifacts",
  };
  let tasksUnknown = false;
  let unplacedGenerators = 0;
  let status: ProtoData["status"] = "ok";
  const branch = { ...BRANCH };

  const setRepo = (i: number, fn: (r: Repo) => Repo) => {
    repos = repos.map((r, j) => (j === i ? fn(r) : r));
  };
  const failGenerator = () =>
    setRepo(0, (r) => ({ ...r, generators: [FAILED_GENERATOR, ...r.generators.slice(1)] }));
  const failArtifacts = () => {
    artifacts = {
      state: "failed",
      failed: 180,
      running: 0,
      total: 300,
      taskId: "task-artifacts",
      message: "180 of 300 artifacts failed to render: generator output missing for 7 targets.",
    };
  };

  switch (scenario) {
    case "incident":
      setRepo(1, (r) => withImportError(r, IMPORT_ERRORS[0] as ImportError, 3));
      failGenerator();
      failArtifacts();
      unplacedGenerators = 1;
      break;
    case "import-error":
      setRepo(1, (r) => withImportError(r, IMPORT_ERRORS[0] as ImportError, 3));
      break;
    case "generator-failed":
      failGenerator();
      failArtifacts();
      break;
    case "running":
      setRepo(2, (r) => ({ ...r, gitState: "syncing", upstream: "9c01d2e", behind: 2 }));
      setRepo(0, (r) => ({
        ...r,
        generators: [
          {
            ...FAILED_GENERATOR,
            state: "running",
            failedTargets: undefined,
            message: undefined,
            updatedAt: ago(1),
          },
        ],
      }));
      artifacts = {
        state: "running",
        failed: 0,
        running: 212,
        total: 300,
        taskId: "task-artifacts",
      };
      break;
    case "many-errors":
      [1, 2, 6, 11, 17].forEach((idx, k) =>
        setRepo(idx, (r) => withImportError(r, IMPORT_ERRORS[k] as ImportError, k + 1))
      );
      failGenerator();
      break;
    case "tasks-unknown":
      tasksUnknown = true;
      break;
    case "no-repos":
      repos = [];
      artifacts = null;
      branch.syncWithGit = false;
      break;
    case "loading":
      status = "loading";
      break;
    case "denied":
      status = "denied";
      break;
    default:
      break;
  }

  if (!hasUpstream) {
    repos = repos.map((r) => ({
      ...r,
      upstream: undefined,
      behind: undefined,
      lastImport: undefined,
    }));
  }

  return {
    branch,
    status,
    repos,
    artifacts,
    tasksUnknown,
    unplacedGenerators,
    branchTasks: BRANCH_TASKS,
    tasks: status === "ok" && !tasksUnknown ? buildTasks(repos, artifacts) : [],
  };
}

const logsFor = (state: TaskState, at: string, message?: string): TaskLog[] => {
  const logs: TaskLog[] = [{ severity: "info", message: "Task started", at }];
  if (state === "FAILED" && message) logs.push({ severity: "error", message, at });
  if (state === "COMPLETED") logs.push({ severity: "info", message: "Task completed", at });
  return logs;
};

function buildTasks(repos: Repo[], artifacts: ArtifactsSummary | null): TaskRow[] {
  const rows: TaskRow[] = [];
  for (const r of repos) {
    const at = r.lastImport ?? ago(9);
    if (r.importError) {
      const message = r.importError.detail
        .map((p) => (typeof p === "string" ? p : p.code))
        .join("");
      rows.push({
        id: r.importError.taskId,
        title: "Import objects from git repository",
        state: "FAILED",
        workflow: "Import",
        related: r.name,
        updatedAt: at,
        logs: logsFor("FAILED", at, `${r.importError.title}: ${message}`),
      });
    } else {
      const state: TaskState = r.gitState === "syncing" ? "RUNNING" : "COMPLETED";
      rows.push({
        id: `imp-${r.id}`,
        title: r.readOnly
          ? "Import last commit from read only git repository"
          : "Import objects from git repository",
        state,
        workflow: "Import",
        related: r.name,
        updatedAt: at,
        logs: logsFor(state, at),
      });
    }
    for (const g of r.generators) {
      const state: TaskState =
        g.state === "failed" ? "FAILED" : g.state === "running" ? "RUNNING" : "COMPLETED";
      rows.push({
        id: g.taskId,
        title: `Generator ${g.definition} run on ${g.targets} targets`,
        state,
        workflow: "Generator",
        related: r.name,
        updatedAt: g.updatedAt,
        logs: logsFor(state, g.updatedAt, g.message),
      });
    }
  }
  if (artifacts) {
    const state: TaskState =
      artifacts.state === "failed"
        ? "FAILED"
        : artifacts.state === "running"
          ? "RUNNING"
          : "COMPLETED";
    rows.push({
      id: artifacts.taskId,
      title: `Generate ${artifacts.total} artifacts`,
      state,
      workflow: "Artifacts",
      related: "Artifacts",
      updatedAt: ago(3),
      logs: logsFor(state, ago(3), artifacts.message),
    });
  }
  for (const t of BRANCH_TASKS) {
    rows.push({
      id: t.id,
      title: t.title,
      state: t.state,
      workflow: t.title.startsWith("Rebase") ? "Rebase" : "Validate",
      related: "This branch",
      updatedAt: t.updatedAt,
      logs: logsFor(t.state, t.updatedAt),
    });
  }
  return rows.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

// ----- Readiness: blockers come from sync_status, warnings from task results -----

export type Blocker = { key: string; repo: Repo; error: ImportError };

export type Warning = {
  key: string;
  kind: "failed" | "running" | "unknown";
  subject: string;
  detail: string;
  repoName?: string;
  message?: string;
  taskId?: string;
};

export type Readiness =
  | { verdict: "checking" }
  | { verdict: "blocked"; blockers: Blocker[]; warnings: Warning[] }
  | { verdict: "warn"; warnings: Warning[] }
  | { verdict: "clear"; empty: boolean };

export function computeReadiness(data: ProtoData): Readiness {
  if (data.status === "loading") return { verdict: "checking" };

  if (data.status === "denied") {
    return {
      verdict: "warn",
      warnings: [
        {
          key: "denied",
          kind: "unknown",
          subject: "Repositories",
          detail: "You can't view this branch's repositories, so their import state is unknown.",
        },
      ],
    };
  }

  const blockers: Blocker[] = data.repos.flatMap((r) =>
    r.gitState === "import-error" && r.importError
      ? [{ key: r.id, repo: r, error: r.importError }]
      : []
  );

  const warnings: Warning[] = data.repos
    .filter((r) => r.gitState === "syncing")
    .map((r) => ({
      key: `${r.id}-sync`,
      kind: "running",
      subject: r.name,
      detail: "Import still running",
    }));

  if (data.tasksUnknown) {
    warnings.push({
      key: "tasks",
      kind: "unknown",
      subject: "Generators and artifacts",
      detail: "Task results didn't load, so generator and artifact runs weren't checked.",
    });
  } else {
    for (const r of data.repos) {
      for (const g of r.generators) {
        if (g.state === "failed") {
          warnings.push({
            key: `${r.id}-${g.definition}`,
            kind: "failed",
            subject: g.definition,
            detail: `Generator failed on ${g.failedTargets ?? "some"} of ${g.targets} targets`,
            repoName: r.name,
            message: g.message,
            taskId: g.taskId,
          });
        } else if (g.state === "running") {
          warnings.push({
            key: `${r.id}-${g.definition}`,
            kind: "running",
            subject: g.definition,
            detail: `Generator still running on ${g.targets} targets`,
            repoName: r.name,
            taskId: g.taskId,
          });
        }
      }
    }
    const a = data.artifacts;
    if (a?.state === "failed") {
      warnings.push({
        key: "artifacts",
        kind: "failed",
        subject: "Artifacts",
        detail: `${a.failed} of ${a.total} failed to render`,
        message: a.message,
        taskId: a.taskId,
      });
    } else if (a?.state === "running") {
      warnings.push({
        key: "artifacts",
        kind: "running",
        subject: "Artifacts",
        detail: `${a.running} of ${a.total} still generating`,
        taskId: a.taskId,
      });
    }
  }

  if (blockers.length) return { verdict: "blocked", blockers, warnings };
  if (warnings.length) return { verdict: "warn", warnings };
  return { verdict: "clear", empty: data.repos.length === 0 };
}
