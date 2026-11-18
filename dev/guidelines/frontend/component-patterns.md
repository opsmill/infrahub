# Component Patterns

> Part of: `dev/guidelines/frontend/`

## Reuse Before Reinvent

Before adding a component or applying the same UI change in multiple places, consult the inventories and search existing implementations:

1. `dev/knowledge/frontend/shared-components.md` — full primitive map
2. `dev/knowledge/frontend/design-system.md` — `@infrahub/ui` package
3. `rg -i "<name-or-behavior>" frontend/app/src/` — components and their callers across all application layers
4. `rg -i "<name>" frontend/app/src/shared/components/`
5. `rg -i "<name>" frontend/packages/ui/src/components/`

If an existing component serves the same responsibility, **compose or extend it** to add the missing behavior. Examples:

- Need a peer picker with a paste-UUID toggle? Wrap `PeerInput` and add the toggle.
- Need a card with a custom header slot? Extend `Card`/`CardHeader` in `@infrahub/ui`, not in feature code.
- Need a single-object lookup by UUID? Use `useGetObject` — never hand-roll a `gql` string.

If you genuinely need a new primitive:

- Justify it in the PR description ("evaluated `PeerInput`, `Combobox`, `RelationshipComboboxList` — none cover X because Y").
- Add an entry to `shared-components.md` so the next person finds it.
- Keep entity-specific components in the owning entity's `ui/`, even when several consumers reuse them. Use `shared/components/` for entity-agnostic components and `frontend/packages/ui/` for design-system primitives. Follow the [architecture dependency rules](../../knowledge/frontend/architecture.md).

Reuse stops at the component's contract. If your data cannot satisfy a shared component's prop type —
your query selects four of `Dropdown`'s twelve fields — do not reshape the shared component's props to
fit (switching its `Dropdown` prop to `Pick<Dropdown, …>`), and do not fabricate the missing fields to
squeeze through it. Build a small feature-local component over
your own row type and leave the shared one to the callers it is named for. (Adding an optional,
default-preserving prop is fine — weakening the type contract is not.)

### Anti-patterns

| Anti-pattern | Replacement |
|---|---|
| `<section className="rounded-md border bg-white p-4 shadow-lg">…</section>` | `Card` from `@infrahub/ui` |
| Hand-rolled `gql` + `graphqlClient.query(...)` for a single node | `useGetObject({ objectId, objectSchema: { kind: "CoreNode" } })` |
| Reinvented kind combobox + object combobox | Wrap `PeerInput` (`shared/components/inputs/peer.tsx`) |
| Custom dialog with focus trap | `Modal` from `@infrahub/ui` |
| `<button className="bg-custom-blue-700 …">` | `Button` from `@infrahub/ui` |

## Extract repeated UI behavior during implementation

When a requirement makes multiple components repeat the same UI responsibility, **extract that
responsibility into a reusable component in the same PR**. Do this as part of implementation and
self-review; do not wait for the user or reviewer to request it. Two call sites are enough when
their behavior must change together. This applies to styling changes as well as new functionality.

1. Search for the behavior being changed, including existing component usages, metadata wiring,
   interaction classes, and action controls. Check sibling render paths such as attributes,
   single relationships, and relationship list items.
2. Reuse or compose existing components first. Extract a cohesive responsibility, such as a
   metadata control with its reveal behavior. Moving only a class string into a constant leaves
   duplicated markup and interaction logic behind.
3. Represent supported differences with typed props or slots. Keep field-specific decisions at
   the caller; avoid a general-purpose component with unrelated modes or a growing set of boolean
   flags. Preserve hover boundaries, keyboard access, permissions, and layout at every call site.
4. Replace the equivalent copies within the feature being changed and document the reusable
   component in the [inventory](../../knowledge/frontend/shared-components.md). Validate meaningful
   differences between callers, especially nested interactions that a standalone test can miss.

Similar markup alone does not require an abstraction. Keep components separate when they own
different behavior or are expected to evolve independently; explain that distinction in the PR
if the change still repeats a substantial block. Do not generalize for hypothetical future uses
or expand a focused change into a repository-wide refactor.

Before finishing, check the diff for the same requirement implemented in several places. A
future change to that shared behavior should have one implementation to update. For example,
`FieldMetadataPopover` owns the metadata mapping and reveal styles for attribute and relationship
rows, while callers supply the popover title and edit action and mark the element whose hover
reveals the icon.

### Add a variant by passing what differs

When a new kind, action or tab needs what a sibling component already does, pass the differences to
that component instead of copying its file. A copy misses every later fix to the original, and the
values left unchanged by mistake, such as toast IDs, log messages and conditions, keep the
original's meaning.

```tsx
// ❌ remove-from-groups-action.tsx copied from add-to-groups-action.tsx with a new label and mutation
// ✅ One component; each caller passes its label, variant and mutation
<GroupsAction label="Add to groups" variant="outline" mutateMembers={addRelationships} />
<GroupsAction label="Remove from groups" variant="danger-outline" mutateMembers={removeRelationships} />
```

When each kind needs a fixed set of values, keep them in one typed record keyed by the kind, so a
caller cannot pair one kind's values with another kind's.

### Make a change in one place

When a change edits the same block in more than one file, such as a component migration, a theme
token or a bug fix, extract the block first and then make the change once. Edits made copy by copy
miss copies: a theme change that reached three of five copies of one list item left two with the
old color.

Find the copies by the block's literals rather than by a component name, and list the files that
past commits changed together with the file you are editing:

```bash
rg -l '<a data-testid, label, toast message or class string from the block>' frontend/app/src
git log --format=%H -- <file> | xargs -n1 git show --format= --name-only | sort | uniq -c | sort -rn | head
```

## Early Return Style

Use early returns instead of nested ternaries for components with multiple states.

```tsx
// ❌ Bad: Nested ternaries
function MyComponent() {
  return (
    <Container>
      {isPending ? (
        <Loading />
      ) : error ? (
        <Error />
      ) : isSuccess ? (
        <Success />
      ) : (
        <Default />
      )}
    </Container>
  );
}

// ✅ Good: Early returns
function MyComponent() {
  if (isPending) {
    return <Container><Loading /></Container>;
  }

  if (error) {
    return <Container><Error /></Container>;
  }

  if (isSuccess) {
    return <Container><Success /></Container>;
  }

  return <Container><Default /></Container>;
}
```

### State Order

For mutation-based components, check states in this order:

1. `isPending` - loading state
2. `error` - error state
3. `isSuccess` - success state
4. Default - initial state

### Inactive states: dim, don't disable

A state that only *looks* inactive (nothing to act on, but the tooltip still explains it) keeps the
same focusable element as every other state, dimmed with an opacity class (`opacity-60`). Disabling
removes it from hover/focus, and swapping element types between states (`Button` in one, `LinkButton`
in another) remounts the subtree, changes the ARIA role mid-session, and breaks role-based selectors
in e2e tests. Reserve disabling for a control whose action must actually be blocked; when that control
still needs its tooltip, `Button`'s `isDisabledAndFocusable` keeps it hoverable and focusable.

## Layout Extraction

When multiple early returns share structure, extract a layout component.

```tsx
// ❌ Bad: Duplicated structure
function CheckConnectivity() {
  if (isPending) {
    return (
      <Col className="gap-4 p-2">
        <Heading>Loading...</Heading>
        <p>Please wait</p>
        <Row>{/* buttons */}</Row>
      </Col>
    );
  }

  if (error) {
    return (
      <Col className="gap-4 p-2">
        <Heading>Error</Heading>
        <p>{error.message}</p>
        <Row>{/* buttons */}</Row>
      </Col>
    );
  }
  // ...
}

// ✅ Good: Shared layout component
interface LayoutProps {
  title: string;
  description: string;
  actions: React.ReactNode;
}

function Layout({ title, description, actions }: LayoutProps) {
  return (
    <Col className="gap-4 p-2">
      <Heading>{title}</Heading>
      <p>{description}</p>
      <Row>{actions}</Row>
    </Col>
  );
}

function CheckConnectivity() {
  if (isPending) {
    return <Layout title="Loading..." description="Please wait" actions={/* ... */} />;
  }

  if (error) {
    return <Layout title="Error" description={error.message} actions={/* ... */} />;
  }
  // ...
}
```

### When to Extract

- Multiple returns share the same wrapper responsibility; do not wait for a third copy when they must change together
- Wrapper has styling or layout logic
- Structure is unlikely to diverge between states

## Aria Overlay Open State

Always pass the boolean to `isOpen`. Don't conditionally render the overlay — it needs to stay mounted to animate closed.

```tsx
// ❌ Bad: unmounts before exit animation
{showConfirm && (
  <Modal isOpen={true} onOpenChange={() => setShowConfirm(false)}>
    {/* ... */}
  </Modal>
)}

// ✅ Good: Modal stays mounted, animates open and close
<Modal isOpen={showConfirm} onOpenChange={() => setShowConfirm(false)}>
  {/* ... */}
</Modal>
```

Applies to all react-aria overlays in `src/shared/components/aria/` (`Sheet`, `Modal`, `Popover`, `Tooltip`).

## Comments

Comment the non-obvious *why* — rationale, gotchas, invariants. Never narrate the *what*: the code already shows it, and a comment restating it is noise that rots as the code changes.

```tsx
// ❌ Bad: narrating what the next line does
// compose the cards directly
<Col>{cards}</Col>

// ✅ Good: a why the reader can't see, or no comment at all
// ObjectDetails owns the useTitle call; composing cards here bypasses it, so set the title explicitly
useTitle(account.display_label);
<Col>{cards}</Col>
```

This is the single most common review nit on agent-written PRs. If you catch yourself writing `// <verb> the <noun>`, delete it.
