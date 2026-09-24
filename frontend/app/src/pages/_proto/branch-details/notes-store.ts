/**
 * Where design-jam notes live. Prototype-only — never shipped.
 *
 * Two backends behind one interface:
 *
 * - `local`   — localStorage. One browser, one reviewer. Always available. This is what a
 *               dev server run uses, and the fallback everywhere else.
 * - `infrahub` — nodes of kind `DesignJamNote` on the instance the prototype is running
 *               in. Every reviewer on a preview sees every pin; the author comes free from
 *               the session; nothing needs a credential in the build because the browser
 *               already has one. Requires the schema to be loaded once per instance — see
 *               `enableSharedNotes()`.
 *
 * Consistency without live updates comes from structure, not sync: one node per note,
 * append-only, so concurrent pins never overwrite each other. Freshness comes from
 * TanStack Query — poll while visible, refetch on focus, refetch after our own writes —
 * the same pattern the app already uses for tasks and proposed-change events. Deletion is
 * a soft `status: deleted` so a polling client converges instead of watching a pin vanish
 * under its cursor.
 *
 * Imports below assume the prototype sits inside the app; adapt the paths on copy.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { jsonToGraphQLQuery } from "json-to-graphql-query";
import { useEffect, useState } from "react";

import { graphql, graphqlClient } from "@/shared/api/graphql/client";
import { constructPath, fetchUrl } from "@/shared/api/rest/fetch";

import { useAuth } from "@/entities/authentication/ui/auth-provider";

export type NoteStatus = "open" | "addressed" | "declined" | "deferred" | "deleted";

export type Note = {
  id: string;
  /** `<slug>:<variant>:rev<N>` — a pin belongs to one screen. */
  scope: string;
  selector: string;
  snippet: string;
  /** Fractions of the pane box, so pins survive a resize. */
  x: number;
  y: number;
  text: string;
  status: NoteStatus;
  resolution?: string;
  /** Display name from the session. `local` notes have none. */
  author?: string;
  /** Account id, for "is this mine". */
  authorId?: string;
  createdAt: string;
  /** Local-only: set once the note has gone through Send. */
  sentAt?: string;
};

export type NewNote = Omit<Note, "id" | "status" | "createdAt" | "author" | "authorId">;

export type Backend = "local" | "infrahub";

const KIND = "DesignJamNote";
const PREFIX = "design-jam:notes:";
const QUERY_ROOT = ["design-jam", "notes"] as const;

/* ---------------------------------------------------------------- local backend */

const readLocal = (scope: string): Note[] => {
  try {
    return JSON.parse(localStorage.getItem(`${PREFIX}${scope}`) ?? "[]");
  } catch {
    return [];
  }
};

const writeLocal = (scope: string, notes: Note[]) => {
  try {
    localStorage.setItem(`${PREFIX}${scope}`, JSON.stringify(notes));
  } catch {
    /* private window or blocked storage — the session still works, it just won't persist */
  }
};

const readAllLocal = (slug: string): Record<string, Note[]> => {
  const out: Record<string, Note[]> = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (!key?.startsWith(`${PREFIX}${slug}:`)) continue;
      const scope = key.slice(PREFIX.length);
      const notes = readLocal(scope).filter((n) => n.text.trim() && n.status !== "deleted");
      if (notes.length) out[scope] = notes;
    }
  } catch {
    /* fine */
  }
  return out;
};

/* ------------------------------------------------------------- infrahub backend */

const NODE_FIELDS = {
  id: true,
  scope: { value: true },
  selector: { value: true },
  snippet: { value: true },
  x: { value: true },
  y: { value: true },
  text: { value: true },
  status: { value: true },
  resolution: { value: true },
};

type Edge = {
  node: {
    id: string;
    scope: { value: string };
    selector: { value: string };
    snippet: { value: string | null };
    x: { value: string };
    y: { value: string };
    text: { value: string | null };
    status: { value: NoteStatus };
    resolution: { value: string | null };
  };
  node_metadata?: {
    created_at?: string;
    created_by?: { id?: string; display_label?: string } | null;
  };
};

const fromEdge = (e: Edge): Note => ({
  id: e.node.id,
  scope: e.node.scope.value,
  selector: e.node.selector.value,
  snippet: e.node.snippet.value ?? "",
  x: Number(e.node.x.value),
  y: Number(e.node.y.value),
  text: e.node.text.value ?? "",
  status: e.node.status.value ?? "open",
  resolution: e.node.resolution.value ?? undefined,
  author: e.node_metadata?.created_by?.display_label ?? undefined,
  authorId: e.node_metadata?.created_by?.id ?? undefined,
  createdAt: e.node_metadata?.created_at ?? new Date().toISOString(),
});

const listQuery = (filter: Record<string, string>) =>
  jsonToGraphQLQuery({
    query: {
      [KIND]: {
        __args: filter,
        edges: {
          node: NODE_FIELDS,
          node_metadata: { created_at: true, created_by: { id: true, display_label: true } },
        },
      },
    },
  });

const fetchInfrahub = async (filter: Record<string, string>): Promise<Note[]> => {
  const { data, errors } = await graphqlClient.query<{ [KIND]?: { edges: Edge[] } }>({
    query: graphql(listQuery(filter)),
  });
  if (errors?.length) throw new Error(errors[0]?.message ?? "notes query failed");
  return (data?.[KIND]?.edges ?? []).map(fromEdge).filter((n) => n.status !== "deleted");
};

const createInfrahub = async (slug: string, note: NewNote) => {
  const [, variant, revPart] = note.scope.split(":");
  const mutation = jsonToGraphQLQuery({
    mutation: {
      [`${KIND}Create`]: {
        __args: {
          data: {
            slug: { value: slug },
            scope: { value: note.scope },
            variant: { value: variant ?? "" },
            rev: { value: Number((revPart ?? "rev0").replace("rev", "")) },
            selector: { value: note.selector },
            snippet: { value: note.snippet },
            x: { value: String(note.x) },
            y: { value: String(note.y) },
            text: { value: note.text },
            status: { value: "open" },
          },
        },
        ok: true,
        object: { id: true },
      },
    },
  });
  const { errors } = await graphqlClient.mutate({ mutation: graphql(mutation) });
  if (errors?.length) throw new Error(errors[0]?.message ?? "note create failed");
};

const updateInfrahub = async (
  id: string,
  patch: Partial<Pick<Note, "text" | "status" | "resolution">>
) => {
  const data: Record<string, unknown> = { id };
  if (patch.text !== undefined) data.text = { value: patch.text };
  if (patch.status !== undefined) data.status = { value: patch.status };
  if (patch.resolution !== undefined) data.resolution = { value: patch.resolution };
  const mutation = jsonToGraphQLQuery({
    mutation: { [`${KIND}Update`]: { __args: { data }, ok: true } },
  });
  const { errors } = await graphqlClient.mutate({ mutation: graphql(mutation) });
  if (errors?.length) throw new Error(errors[0]?.message ?? "note update failed");
};

/**
 * Is the kind loaded on this instance? A query against an unknown type errors — that is
 * the probe. Cached per page load; "Enable shared notes" re-probes.
 */
const probeInfrahub = async (): Promise<boolean> => {
  try {
    const { errors } = await graphqlClient.query({
      query: graphql(
        jsonToGraphQLQuery({ query: { [KIND]: { __args: { limit: 1 }, count: true } } })
      ),
      // Local fix: an unknown kind is the expected answer, not an error. Without a handler the
      // app's client shows "Cannot query field 'DesignJamNote'" as a toast on every page load.
      context: { processErrorMessage: () => undefined },
    });
    return !errors?.length;
  } catch {
    return false;
  }
};

/**
 * Loads the DesignJamNote schema onto the current instance. Admin only, once per instance,
 * and only ever on a preview. The body mirrors `design-jam-notes.schema.yml`; keep them in
 * step. Infrahub applies a schema load as a migration, so this takes a few seconds.
 */
export const enableSharedNotes = async () => {
  const schema = {
    version: "1.0",
    nodes: [
      {
        name: "Note",
        namespace: "DesignJam",
        label: "Design note",
        include_in_menu: false,
        branch: "agnostic",
        generate_profile: false,
        display_label: "{{ snippet__value }}",
        attributes: [
          { name: "slug", kind: "Text" },
          { name: "scope", kind: "Text" },
          { name: "variant", kind: "Text" },
          { name: "rev", kind: "Number" },
          { name: "selector", kind: "Text" },
          { name: "snippet", kind: "Text", optional: true },
          { name: "x", kind: "Text" },
          { name: "y", kind: "Text" },
          { name: "text", kind: "TextArea", optional: true },
          {
            name: "status",
            kind: "Dropdown",
            default_value: "open",
            choices: ["open", "addressed", "declined", "deferred", "deleted"].map((name) => ({
              name,
            })),
          },
          { name: "resolution", kind: "Text", optional: true },
        ],
      },
    ],
  };
  await fetchUrl(constructPath("/api/schema/load"), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ schemas: [schema] }),
  });
};

/* ------------------------------------------------------------------------ hook */

export type NotesStore = {
  backend: Backend;
  /** Notes on the current scope, minus soft-deleted. */
  notes: Note[];
  /** Whether the current session may edit a note: local always; shared only its author. */
  isMine: (n: Note) => boolean;
  add: (note: NewNote) => Promise<void>;
  update: (
    id: string,
    patch: Partial<Pick<Note, "text" | "status" | "resolution" | "sentAt">>
  ) => Promise<void>;
  remove: (id: string) => Promise<void>;
  /** Every non-deleted note on the run, keyed by scope — the owner's "copy all". */
  all: () => Promise<Record<string, Note[]>>;
  refresh: () => Promise<unknown>;
  /** When the shared list was last confirmed fresh; undefined for local. */
  updatedAt?: number;
  isFetching: boolean;
  /** Shared notes are possible here but the kind is not loaded yet. */
  canEnable: boolean;
  enable: () => Promise<void>;
};

const POLL_MS = 15_000;

export function useNotesStore(slug: string, scope: string): NotesStore {
  const { isAuthenticated, user } = useAuth();
  const qc = useQueryClient();

  // Start on local, probe once, switch if the kind exists. A page that opens on local and
  // flips to shared a second later is better than one that waits on a network round-trip
  // before it can show anything.
  const [backend, setBackend] = useState<Backend>("local");
  const [probed, setProbed] = useState(false);
  useEffect(() => {
    if (!isAuthenticated) {
      setProbed(true);
      return;
    }
    probeInfrahub().then((ok) => {
      setBackend(ok ? "infrahub" : "local");
      setProbed(true);
    });
  }, [isAuthenticated]);

  const shared = backend === "infrahub";

  const query = useQuery({
    queryKey: [...QUERY_ROOT, slug, scope],
    queryFn: () => fetchInfrahub({ slug__value: slug, scope__value: scope }),
    enabled: shared,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    staleTime: 5000,
  });

  const [localNotes, setLocalNotes] = useState<Note[]>(() => readLocal(scope));
  useEffect(() => {
    setLocalNotes(readLocal(scope));
  }, [scope]);

  const commitLocal = (next: Note[]) => {
    setLocalNotes(next);
    writeLocal(scope, next);
  };

  const invalidate = () => qc.invalidateQueries({ queryKey: [...QUERY_ROOT, slug] });

  const notes = shared ? (query.data ?? []) : localNotes.filter((n) => n.status !== "deleted");

  return {
    backend,
    notes,
    isMine: (n) => !shared || !n.authorId || n.authorId === user?.id,

    add: async (note) => {
      if (shared) {
        await createInfrahub(slug, note);
        await invalidate();
        return;
      }
      commitLocal([
        ...localNotes,
        {
          ...note,
          id: `n${Date.now().toString(36)}`,
          status: "open",
          createdAt: new Date().toISOString(),
        },
      ]);
    },

    update: async (id, patch) => {
      if (shared) {
        const { sentAt: _ignored, ...rest } = patch;
        await updateInfrahub(id, rest);
        await invalidate();
        return;
      }
      commitLocal(localNotes.map((n) => (n.id === id ? { ...n, ...patch } : n)));
    },

    remove: async (id) => {
      if (shared) {
        await updateInfrahub(id, { status: "deleted" });
        await invalidate();
        return;
      }
      commitLocal(localNotes.filter((n) => n.id !== id));
    },

    all: async () => {
      if (!shared) return readAllLocal(slug);
      const flat = await fetchInfrahub({ slug__value: slug });
      const out: Record<string, Note[]> = {};
      for (const n of flat) {
        if (!n.text.trim()) continue;
        (out[n.scope] ??= []).push(n);
      }
      return out;
    },

    refresh: () => (shared ? query.refetch() : Promise.resolve()),
    updatedAt: shared ? query.dataUpdatedAt : undefined,
    isFetching: shared && query.isFetching,
    canEnable: probed && isAuthenticated && !shared,
    enable: async () => {
      await enableSharedNotes();
      // Schema loads are applied asynchronously; give it a moment, then re-probe.
      await new Promise((r) => setTimeout(r, 2500));
      const ok = await probeInfrahub();
      setBackend(ok ? "infrahub" : "local");
      if (ok) await invalidate();
    },
  };
}
