// PROTOTYPE — throwaway, delete with the /_proto route. Mocked worst-case data, limited to what
// the backend returns today: no upstream head, no last-import time, and import errors are the raw
// last error line of the import task's log.

export type GitState = "in-sync" | "import-error" | "syncing" | "unknown";
export type RunState = "failed" | "running" | "passed";

// Colours mirror the CoreRepository.sync_status dropdown values used by the IFC-3200 canvas.
export const GIT_STATE: Record<GitState, { label: string; color: string }> = {
  "in-sync": { label: "In Sync", color: "#60a5fa" },
  "import-error": { label: "Import Error", color: "#f87171" },
  syncing: { label: "Syncing", color: "#fcd34d" },
  unknown: { label: "Unknown", color: "#d6d3d1" },
};

// CoreGenericRepository.operational_status: whether Infrahub can reach the remote at all.
export type Operational = "online" | "error-cred" | "error-connection" | "error" | "unknown";

export const OPERATIONAL_ERROR: Partial<Record<Operational, string>> = {
  "error-cred": "Credentials rejected by the remote",
  "error-connection": "Can't connect to the remote",
  error: "Remote returned an error",
};

export type ImportError = {
  /** Last error-severity log line of the latest import task, verbatim. */
  message: string;
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
  operational: Operational;
  importError?: ImportError;
  generators: GeneratorRun[];
};

// Counts of CoreArtifact.status on the branch: failed = Error, running = Pending + Processing.
// No single task covers them, so the link goes to the filtered artifact list.
export type ArtifactsSummary = {
  state: RunState;
  failed: number;
  running: number;
  total: number;
};

export const FAILED_ARTIFACTS_HREF = "/objects/CoreArtifact?filters=status__value:Error";

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
  | "unreachable"
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
  { id: "unreachable", label: "Remote unreachable (warn)" },
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
    message:
      "Unable to load the schema file schemas/site_fra1.yml: [Errno 2] No such file or directory",
    taskId: "task-import-1",
  },
  {
    message:
      "1 validation error for InfrahubRepositoryConfig\ntransforms: names must be unique, 'device_interfaces' is defined 2 times",
    taskId: "task-import-2",
  },
  {
    message:
      "Unable to find the group edge_routers used as targets by artifact definition 'edge_config'",
    taskId: "task-import-3",
  },
  {
    message:
      "Schema update rejected: InfraDevice.asn: kind can't change from Number to Text without a migration",
    taskId: "task-import-4",
  },
  {
    message: "ModuleNotFoundError: No module named 'netutils' (transforms/interfaces.py)",
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
    operational: "online",
    generators: [ok("dc-fabric-leaf-spine", 48, 6), ok("dc-fabric-underlay", 12, 6)],
  },
  {
    id: "r2",
    name: "infrastructure-templates",
    readOnly: false,
    gitState: "in-sync",
    commit: "8f3c2a1",
    operational: "online",
    generators: [],
  },
  {
    id: "r3",
    name: "network-services",
    readOnly: false,
    gitState: "in-sync",
    commit: "61ba9c3",
    operational: "online",
    generators: [ok("edge-peering", 12, 5)],
  },
  {
    id: "r4",
    name: "vendor-golden-configs",
    readOnly: true,
    gitState: "in-sync",
    commit: "v2.4.1 · 77aa01b",
    operational: "online",
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
    operational: "online",
    generators: n % 4 === 0 ? [ok(`site-${n}`, 3, 8 + n)] : [],
  };
};

const withImportError = (repo: Repo, error: ImportError): Repo => ({
  ...repo,
  gitState: "import-error",
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

export function buildData(scenario: Scenario, repoCount: number): ProtoData {
  const pool = [...BASE];
  const wanted = scenario === "many-errors" ? 40 : Math.max(1, repoCount);
  for (let n = 1; pool.length < wanted; n++) pool.push(filler(n));
  let repos = pool.slice(0, wanted);

  let artifacts: ArtifactsSummary | null = {
    state: "passed",
    failed: 0,
    running: 0,
    total: 300,
  };
  let tasksUnknown = false;
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
    };
  };

  switch (scenario) {
    case "incident":
      setRepo(1, (r) => withImportError(r, IMPORT_ERRORS[0] as ImportError));
      failGenerator();
      failArtifacts();
      break;
    case "import-error":
      setRepo(1, (r) => withImportError(r, IMPORT_ERRORS[0] as ImportError));
      break;
    case "generator-failed":
      failGenerator();
      failArtifacts();
      break;
    case "unreachable":
      setRepo(2, (r) => ({ ...r, operational: "error-cred" }));
      break;
    case "running":
      setRepo(2, (r) => ({ ...r, gitState: "syncing" }));
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
      };
      break;
    case "many-errors":
      [1, 2, 6, 11, 17].forEach((idx, k) =>
        setRepo(idx, (r) => withImportError(r, IMPORT_ERRORS[k] as ImportError))
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

  return {
    branch,
    status,
    repos,
    artifacts,
    tasksUnknown,
    branchTasks: BRANCH_TASKS,
    tasks:
      status === "loading" || tasksUnknown
        ? []
        : buildTasks(status === "denied" ? [] : repos, status === "denied" ? null : artifacts),
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
  for (const [i, r] of repos.entries()) {
    const at = ago(5 + i);
    if (r.importError) {
      rows.push({
        id: r.importError.taskId,
        title: "Import objects from git repository",
        state: "FAILED",
        workflow: "Import",
        related: r.name,
        updatedAt: at,
        logs: logsFor("FAILED", at, r.importError.message),
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
      id: "task-artifacts",
      title: "Generate artifacts for definition device_config",
      state,
      workflow: "Artifacts",
      related: "Artifacts",
      updatedAt: ago(3),
      logs: logsFor(
        state,
        ago(3),
        "Artifact generation failed for 180 targets: generator output missing for leaf-ams1-r12-07"
      ),
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
  kind: "failed" | "unreachable" | "running" | "unknown";
  subject: string;
  detail: string;
  repoId?: string;
  repoName?: string;
  message?: string;
  taskId?: string;
  href?: string;
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

  const warnings: Warning[] = data.repos.flatMap((r): Warning[] => {
    const unreachable = OPERATIONAL_ERROR[r.operational];
    if (unreachable)
      return [
        {
          key: `${r.id}-op`,
          kind: "unreachable",
          subject: r.name,
          detail: `${unreachable}; its commit may be out of date`,
          repoId: r.id,
        },
      ];
    if (r.gitState === "syncing")
      return [
        { key: `${r.id}-sync`, kind: "running", subject: r.name, detail: "Import still running" },
      ];
    return [];
  });

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
        href: FAILED_ARTIFACTS_HREF,
      });
    } else if (a?.state === "running") {
      warnings.push({
        key: "artifacts",
        kind: "running",
        subject: "Artifacts",
        detail: `${a.running} of ${a.total} still generating`,
      });
    }
  }

  if (blockers.length) return { verdict: "blocked", blockers, warnings };
  if (warnings.length) return { verdict: "warn", warnings };
  return { verdict: "clear", empty: data.repos.length === 0 };
}
