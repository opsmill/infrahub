// PROTOTYPE design-jam account-settings — rev-1 building blocks, shared by all four
// directions at rev 1. Frozen: a later revision copies this file, it never edits it.

import { Button, Card, CardContent, CardHeader, Modal, Sheet } from "@infrahub/ui";
import {
  AlertTriangleIcon,
  ClockAlertIcon,
  ClockFadingIcon,
  InfoIcon,
  KeyRoundIcon,
  KeySquareIcon,
  LockKeyholeIcon,
  MonitorIcon,
  MoonIcon,
  PlusIcon,
  SlidersHorizontalIcon,
  SunIcon,
  Trash2Icon,
  UserRoundIcon,
  UsersRoundIcon,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Heading } from "react-aria-components";
import { toast } from "react-toastify";

import { Radio, RadioGroup } from "@/shared/components/aria/radio-group";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Col, Row } from "@/shared/components/container";
import { Avatar } from "@/shared/components/display/avatar";
import ErrorScreen from "@/shared/components/errors/error-screen";
import PasswordInputField from "@/shared/components/form/fields/password-input.field";
import { isRequired } from "@/shared/components/form/utils/validation";
import { DetailsLayout } from "@/shared/components/layout/details-layout";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Badge } from "@/shared/components/ui/badge";
import { Form, type FormRef, FormSubmit } from "@/shared/components/ui/form";
import { inputStyle } from "@/shared/components/ui/style";
import { useFormatDate } from "@/shared/context/date-preferences-context";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { ThemeSchema } from "@/entities/config/domain/model/theme";
import { useTheme } from "@/entities/config/ui/theme-provider";
import { ObjectActivitiesCard } from "@/entities/nodes/object/ui/object-details/object-activities-card";
import { ObjectDetailsCard } from "@/entities/nodes/object/ui/object-details/object-details-card";
import { ObjectProfilesGroupsCard } from "@/entities/nodes/object/ui/object-details/object-profiles-groups-card";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { MANAGE_GLOBAL_PREFERENCES } from "@/entities/permission/domain/model/permission";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { RequireGlobalPermission } from "@/entities/permission/ui/require-global-permission";
import { GlobalPreferencesEditor } from "@/entities/preferences/ui/global-preferences-editor";
import { UserPreferencesCard } from "@/entities/preferences/ui/user-preferences-card";
import { ACCOUNT_GENERIC_OBJECT } from "@/entities/role-manager/domain/model/account";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { useGetAccountProfile } from "@/entities/user-profile/ui/queries/get-account-profile.query";

import type { KnobValue } from "./design-history-panel";
import { FAKE_SECRET, LONG_IDENTITY, MANY_TOKENS, type MockToken, tokenSummary } from "./mock";

/* ------------------------------------------------------------------ knobs → scenario */

export type Scenario = {
  prefsOwnSection: boolean;
  p2: boolean;
  tokens: "many" | "empty" | "error" | "loading";
  externalPassword: boolean;
  admin: boolean;
  longName: boolean;
};

export const toScenario = (k: Record<string, KnobValue>): Scenario => ({
  prefsOwnSection: k.prefs === "own section",
  p2: k.p2 === true,
  tokens: k.tokens as Scenario["tokens"],
  externalPassword: k.password === "external",
  admin: k.admin === true,
  longName: k.longName === true,
});

/* ------------------------------------------------------------------ sections */

export type SectionId = "profile" | "preferences" | "tokens" | "password" | "global";

export type SectionDef = {
  id: SectionId;
  label: string;
  description: string;
  group: "Personal" | "Administration";
  icon: ReactNode;
};

export const sectionsFor = (s: Scenario): SectionDef[] => {
  const all: SectionDef[] = [
    {
      id: "profile",
      label: "Profile",
      description: s.prefsOwnSection
        ? "Your account details, groups and recent activity."
        : "Your account details, preferences, groups and recent activity.",
      group: "Personal",
      icon: <UserRoundIcon className="size-4" />,
    },
    {
      id: "preferences",
      label: "Preferences",
      description: "Theme, date format and timezone, for you only.",
      group: "Personal",
      icon: <SlidersHorizontalIcon className="size-4" />,
    },
    {
      id: "tokens",
      label: "API tokens",
      description: "Authenticate infrahubctl, the Python SDK and API calls.",
      group: "Personal",
      icon: <KeyRoundIcon className="size-4" />,
    },
    {
      id: "password",
      label: "Password",
      description: "The password you sign in with.",
      group: "Personal",
      icon: <LockKeyholeIcon className="size-4" />,
    },
    {
      id: "global",
      label: "Global preferences",
      description: "Date and time defaults for everyone on this instance.",
      group: "Administration",
      icon: <UsersRoundIcon className="size-4" />,
    },
  ];
  return all.filter(
    (d) => (d.id !== "preferences" || s.prefsOwnSection) && (d.id !== "global" || s.admin)
  );
};

/** `?section=` is the prototype's stand-in for a real nested route per section (FR-003). */
export function useSection<T extends SectionId | null>(fallback: T) {
  const read = () =>
    (new URLSearchParams(window.location.search).get("section") as SectionId) ?? fallback;
  const [section, setSection] = useState<SectionId | T>(read);

  useEffect(() => {
    const onPop = () => setSection(read());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  });

  const go = (id: SectionId | null) => {
    const p = new URLSearchParams(window.location.search);
    if (id) p.set("section", id);
    else p.delete("section");
    window.history.pushState(window.history.state, "", `?${p.toString()}`);
    setSection((id ?? fallback) as SectionId | T);
  };

  return [section, go] as const;
}

/** Preferences folded into Profile: a deep link to it must still land somewhere real. */
export const resolveSection = (id: SectionId, defs: SectionDef[]): SectionId =>
  defs.some((d) => d.id === id) ? id : "profile";

/* ------------------------------------------------------------------ identity */

export function useIdentity(s: Scenario) {
  const { data } = useGetAccountProfile();
  if (s.longName) return LONG_IDENTITY;
  return {
    name: data?.name?.value ?? "",
    label: data?.display_label ?? "",
    description: data?.description?.value ?? null,
  };
}

export function IdentityHeader({ s, compact }: { s: Scenario; compact?: boolean }) {
  const id = useIdentity(s);
  return (
    <Row className="min-w-0 items-center gap-3">
      <Avatar name={id.name} size={compact ? "md" : "default"} />
      <div className="min-w-0">
        <div
          className={classNames("truncate font-semibold", !compact && "text-lg")}
          title={id.label}
        >
          {id.label}
        </div>
        {(!s.p2 || id.description) && (
          <p className="truncate text-foreground-muted text-sm">{id.description ?? "-"}</p>
        )}
      </div>
    </Row>
  );
}

/* ------------------------------------------------------------------ small pieces (gaps) */

/** Gap in @infrahub/ui (01-system.md § Missing): a generic empty state with an action. */
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Col className="items-center gap-1 px-6 py-12 text-center">
      <div className="mb-2 flex size-10 items-center justify-center rounded-full bg-content-strong text-foreground-muted">
        {icon}
      </div>
      <div className="font-semibold">{title}</div>
      <p className="max-w-sm text-balance text-foreground-muted text-sm">{children}</p>
      {action && <div className="mt-3">{action}</div>}
    </Col>
  );
}

/** Gap (01-system.md § Close): an in-page callout; `Alert` is shaped for toasts. */
export function Callout({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: "info" | "danger";
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const Icon = tone === "danger" ? AlertTriangleIcon : InfoIcon;
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={classNames(
        "flex items-start gap-3 rounded-xl border p-3 text-sm",
        tone === "danger" ? "border-danger/30 bg-danger-surface" : "bg-content"
      )}
    >
      <Icon
        className={classNames(
          "mt-0.5 size-4 shrink-0",
          tone === "danger" ? "text-danger" : "text-foreground-muted"
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{title}</div>
        {children && <div className="mt-0.5 text-foreground-muted">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <Row className="mb-4 items-start gap-4">
      <div className="min-w-0 flex-1">
        <h2 className="font-semibold text-lg">{title}</h2>
        {description && <p className="text-foreground-muted text-sm">{description}</p>}
      </div>
      {action}
    </Row>
  );
}

/* ------------------------------------------------------------------ Profile */

export function ProfileBody({ s }: { s: Scenario }) {
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT);
  if (!schema) return <ErrorScreen message={`Schema ${ACCOUNT_GENERIC_OBJECT} not found`} />;
  return <ProfileContent schema={schema} withPreferences={!s.prefsOwnSection} />;
}

function ProfileContent({
  schema,
  withPreferences,
}: {
  schema: ModelSchema;
  withPreferences: boolean;
}) {
  const accountId = useAuth().user?.id;
  const object = useGetObject(
    { objectSchema: schema, objectId: accountId ?? "" },
    { enabled: !!accountId }
  );
  const permission = useGetObjectPermissions(schema.kind!);

  if (object.isPending || permission.isPending) return <LoadingIndicator className="h-61" />;
  if (object.error || permission.error) {
    return <ErrorScreen message={object.error?.message || permission.error?.message} />;
  }

  return (
    <DetailsLayout>
      <DetailsLayout.Main>
        <ObjectDetailsCard
          objectSchema={schema}
          objectData={object.data}
          permission={permission.data}
        />
        {withPreferences && <PreferencesBody />}
      </DetailsLayout.Main>
      <DetailsLayout.Aside>
        <ObjectProfilesGroupsCard
          objectSchema={schema}
          objectData={object.data}
          permission={permission.data}
        />
        <ObjectActivitiesCard objectKind={object.data.__typename} objectId={object.data.id} />
      </DetailsLayout.Aside>
    </DetailsLayout>
  );
}

/* ------------------------------------------------------------------ Preferences */

const THEMES = [
  { id: "system", label: "System", icon: MonitorIcon },
  { id: "light", label: "Light", icon: SunIcon },
  { id: "dark", label: "Dark", icon: MoonIcon },
] as const;

export function ThemeCard() {
  const { theme, setTheme } = useTheme();
  return (
    <Card>
      <CardHeader>Theme</CardHeader>
      <CardContent>
        <RadioGroup
          aria-label="Theme"
          orientation="horizontal"
          value={theme}
          onChange={(v) => {
            const parsed = ThemeSchema.safeParse(v);
            if (parsed.success) setTheme(parsed.data);
          }}
          className="gap-2"
        >
          {THEMES.map(({ id, label, icon: Icon }) => (
            <Radio
              key={id}
              value={id}
              className="rounded-xl border px-3 py-2 text-sm data-selected:border-custom-blue-600 data-selected:bg-custom-blue-700/5"
            >
              <Icon className="size-4 text-foreground-muted" />
              {label}
              {id === "dark" && <Badge variant="yellow">alpha</Badge>}
            </Radio>
          ))}
        </RadioGroup>
      </CardContent>
    </Card>
  );
}

export function PreferencesBody() {
  return (
    <Col className="gap-2">
      <ThemeCard />
      <UserPreferencesCard />
    </Col>
  );
}

/* ------------------------------------------------------------------ Tokens */

export function TokensBody({ s, showHeader = true }: { s: Scenario; showHeader?: boolean }) {
  // Keyed by the scenario so flipping the knob resets local create/delete state.
  return <TokensInner key={s.tokens} s={s} showHeader={showHeader} />;
}

function TokensInner({ s, showHeader }: { s: Scenario; showHeader: boolean }) {
  const [tokens, setTokens] = useState<MockToken[]>(s.tokens === "many" ? MANY_TOKENS : []);
  const create = (t: MockToken) => setTokens((prev) => [t, ...prev]);
  const remove = (id: string) => setTokens((prev) => prev.filter((t) => t.id !== id));

  if (!s.p2) {
    return (
      <div className="p-2">
        {showHeader && (
          <div className="mb-4 flex justify-between p-2">
            <div>
              <h1 className="font-semibold text-xl">Infrahub account tokens</h1>
              <p className="text-foreground-muted text-sm">
                Account tokens can be used as an authentication mechanism for Infrahub's REST- and
                GraphQL API, the Python SDK and infrahubctl.
              </p>
            </div>
            <CreateTokenAction onCreate={create} />
          </div>
        )}
        {s.tokens === "loading" ? (
          <LoadingIndicator />
        ) : s.tokens === "error" ? (
          <div>Error: Failed to fetch</div>
        ) : (
          <Card className="divide-y">
            {tokens.map((t) => (
              <TokenRow key={t.id} token={t} onDelete={remove} />
            ))}
          </Card>
        )}
      </div>
    );
  }

  const summary = tokenSummary(tokens);
  return (
    <div>
      {showHeader && (
        <SectionHeader
          title="API tokens"
          description="Tokens authenticate infrahubctl, the Python SDK and calls to the GraphQL and REST APIs. Each one has your full permissions."
          action={
            tokens.length > 0 && s.tokens === "many" ? (
              <CreateTokenAction onCreate={create} />
            ) : undefined
          }
        />
      )}
      {s.tokens === "loading" ? (
        <Card className="divide-y">
          {[0, 1, 2].map((i) => (
            <Row key={i} className="gap-3 p-3">
              <Skeleton className="size-5 rounded" />
              <Col className="flex-1 gap-1.5">
                <Skeleton className="h-3.5 w-48" />
                <Skeleton className="h-3 w-32" />
              </Col>
            </Row>
          ))}
        </Card>
      ) : s.tokens === "error" ? (
        <Callout
          tone="danger"
          title="Couldn't load your tokens"
          action={
            <Button
              size="sm"
              variant="outline"
              onPress={() =>
                toast(<Alert type={ALERT_TYPES.INFO} message="Retrying (prototype)" />)
              }
            >
              Retry
            </Button>
          }
        >
          The server didn't answer. Existing tokens keep working; this only affects the list.
        </Callout>
      ) : tokens.length === 0 ? (
        <Card>
          <EmptyState
            icon={<KeyRoundIcon className="size-5" />}
            title="No API tokens yet"
            action={<CreateTokenAction onCreate={create} label="Create your first token" />}
          >
            Create a token to let a script, a pipeline or infrahubctl act as you. You'll see the
            secret once, right after creating it.
          </EmptyState>
        </Card>
      ) : (
        <>
          {(summary.expired > 0 || summary.noExpiry > 0) && (
            <Row className="mb-2 gap-2 text-sm">
              <span className="text-foreground-muted">{summary.total} tokens</span>
              {summary.expired > 0 && <Badge variant="red">{summary.expired} expired</Badge>}
              {summary.noExpiry > 0 && (
                <Badge variant="yellow">{summary.noExpiry} never expire</Badge>
              )}
            </Row>
          )}
          <Card className="divide-y">
            {tokens.map((t) => (
              <TokenRow key={t.id} token={t} onDelete={remove} />
            ))}
          </Card>
        </>
      )}
    </div>
  );
}

function TokenRow({ token, onDelete }: { token: MockToken; onDelete: (id: string) => void }) {
  return (
    <Row className="gap-3 p-3 text-sm">
      <KeySquareIcon className="size-5 shrink-0 text-foreground-muted" />
      <div className="min-w-0">
        <div className="truncate font-medium" title={token.name}>
          {token.name}
        </div>
        <Expiration date={token.expiration} />
      </div>
      <Button
        variant="ghost"
        shape="square"
        size="sm"
        aria-label={`Delete token ${token.name}`}
        className="ml-auto"
        onPress={() => onDelete(token.id)}
      >
        <Trash2Icon className="size-4" />
      </Button>
    </Row>
  );
}

function Expiration({ date }: { date: string | null }) {
  const { formatDate } = useFormatDate();
  if (!date) {
    return (
      <Row className="text-amber-600">
        <ClockAlertIcon className="size-4" /> This token has no expiration date
      </Row>
    );
  }
  if (new Date(date) < new Date()) {
    return (
      <Row className="text-danger">
        <ClockAlertIcon className="size-4" /> Expired on {formatDate(date, "datetime")}
      </Row>
    );
  }
  return (
    <Row className="text-foreground-muted">
      <ClockFadingIcon className="size-4" /> Expires {formatDate(date, "datetime")}
    </Row>
  );
}

export function CreateTokenAction({
  onCreate,
  label = "Add account token",
}: {
  onCreate: (t: MockToken) => void;
  label?: string;
}) {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [secret, setSecret] = useState("");
  const [name, setName] = useState("");
  const [expiration, setExpiration] = useState("");

  const submit = () => {
    if (!name.trim()) return;
    onCreate({
      id: `new-${Date.now()}`,
      name: name.trim(),
      expiration: expiration ? new Date(expiration).toISOString() : null,
    });
    setIsFormOpen(false);
    setName("");
    setExpiration("");
    setSecret(FAKE_SECRET);
  };

  return (
    <>
      <Button onPress={() => setIsFormOpen(true)}>
        <PlusIcon className="size-4" />
        {label}
      </Button>

      <Sheet isOpen={isFormOpen} onOpenChange={setIsFormOpen} aria-label="Create a new token">
        <Col className="mb-4">
          <h3 className="font-semibold text-lg">Create a new token</h3>
          <span className="text-foreground-muted text-sm">
            These tokens provide full access to your account. Please keep them secure.
          </span>
        </Col>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Name *</span>
            <input
              className={inputStyle}
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Expiration</span>
            <input
              type="datetime-local"
              className={inputStyle}
              value={expiration}
              onChange={(e) => setExpiration(e.target.value)}
            />
          </label>
          <Row className="justify-end gap-2">
            <Button variant="outline" onPress={() => setIsFormOpen(false)}>
              Cancel
            </Button>
            <Button type="submit">Create</Button>
          </Row>
        </form>
      </Sheet>

      <Modal isOpen={!!secret} isDismissable={false} onOpenChange={(o) => !o && setSecret("")}>
        <Col className="p-3">
          <Heading slot="title" className="flex items-center gap-2 font-semibold">
            <KeyRoundIcon className="size-5" />
            Token created
          </Heading>
          <div className="px-8 py-4">
            <p>Please copy your token now.</p>
            <p className="font-semibold">For security reasons we cannot show it again.</p>
          </div>
          <Row>
            <div className={inputStyle}>{secret}</div>
            <CopyToClipboard size="md" text={secret} shape="square" variant="outline" />
          </Row>
        </Col>
        <Row className="justify-end bg-content-muted p-3">
          <Button variant="primary" onPress={() => setSecret("")}>
            Confirm
          </Button>
        </Row>
      </Modal>
    </>
  );
}

/* ------------------------------------------------------------------ Password */

export function PasswordBody({
  s,
  go,
  showHeader = true,
}: {
  s: Scenario;
  go: (id: SectionId) => void;
  showHeader?: boolean;
}) {
  const formRef = useRef<FormRef>(null);

  const onSubmit = async () => {
    await new Promise((r) => setTimeout(r, 400));
    toast(<Alert type={ALERT_TYPES.SUCCESS} message="Password updated" />);
    formRef.current?.reset();
  };

  const fields = (
    <>
      <PasswordInputField
        name="newPassword"
        label="New password"
        rules={{ required: true, validate: { required: isRequired } }}
      />
      <PasswordInputField
        name="confirmPassword"
        label="Confirm password"
        rules={{
          required: true,
          validate: {
            required: isRequired,
            isSamePassword: ({ value }, fieldValues) =>
              value === fieldValues.newPassword.value || "Passwords don't match",
          },
        }}
      />
    </>
  );

  if (!s.p2) {
    return (
      <main className="p-2">
        <Card className="m-auto w-full max-w-md">
          <CardContent>
            {s.externalPassword ? (
              <>
                <h3 className="mb-2 font-semibold leading-6">Password managed externally</h3>
                <p className="text-foreground-muted text-sm">
                  This account authenticates through an external directory. Change your password in
                  the directory provider; local password updates are not accepted.
                </p>
              </>
            ) : (
              <>
                <h3 className="mb-4 font-semibold leading-6">Update your password</h3>
                <Form ref={formRef} onSubmit={onSubmit}>
                  {fields}
                  <FormSubmit>Update password</FormSubmit>
                </Form>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <div className="max-w-xl">
      {showHeader && (
        <SectionHeader
          title="Password"
          description={
            s.externalPassword ? undefined : "The password you sign in to Infrahub with."
          }
        />
      )}
      {s.externalPassword ? (
        <Callout
          title="Your password is managed by your identity provider"
          action={
            <Button size="sm" variant="outline" onPress={() => go("tokens")}>
              API tokens
            </Button>
          }
        >
          You sign in through an external directory, so Infrahub can't change your password. Change
          it there, or ask your administrator. API tokens still work for automation.
        </Callout>
      ) : (
        <Card>
          <CardContent>
            <Form ref={formRef} onSubmit={onSubmit}>
              {fields}
              <FormSubmit>Update password</FormSubmit>
            </Form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ Global preferences */

export function GlobalBody() {
  return (
    <RequireGlobalPermission
      action={MANAGE_GLOBAL_PREFERENCES}
      loadingClassName="h-32"
      unauthorizedMessage="You don't have permission to edit global preferences"
    >
      <GlobalPreferencesEditor />
    </RequireGlobalPermission>
  );
}

/* ------------------------------------------------------------------ dispatch */

export function SectionBody({
  id,
  s,
  go,
  showHeader = true,
}: {
  id: SectionId;
  s: Scenario;
  go: (id: SectionId) => void;
  showHeader?: boolean;
}) {
  switch (id) {
    case "profile":
      return <ProfileBody s={s} />;
    case "preferences":
      return <PreferencesBody />;
    case "tokens":
      return <TokensBody s={s} showHeader={showHeader} />;
    case "password":
      return <PasswordBody s={s} go={go} showHeader={showHeader} />;
    case "global":
      return <GlobalBody />;
  }
}

export const sectionSummary = (id: SectionId, s: Scenario, themeLabel: string): ReactNode => {
  switch (id) {
    case "profile":
      return null;
    case "preferences":
      return `Theme: ${themeLabel}`;
    case "tokens": {
      if (s.tokens === "error") return "Couldn't load tokens";
      if (s.tokens === "loading") return "Loading…";
      if (s.tokens === "empty") return "No tokens yet";
      const t = tokenSummary(MANY_TOKENS);
      return `${t.total} tokens · ${t.expired} expired · ${t.noExpiry} never expire`;
    }
    case "password":
      return s.externalPassword ? "Managed by your identity provider" : null;
    case "global":
      return null;
  }
};
