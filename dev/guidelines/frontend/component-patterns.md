# Component Patterns

> Part of: `dev/guidelines/frontend/`

## Reuse Before Reinvent

Before creating a new picker, combobox, kind selector, card, modal, button, form input, or any component that "feels generic", consult the inventories:

1. `dev/knowledge/frontend/shared-components.md` — full primitive map
2. `dev/knowledge/frontend/design-system.md` — `@infrahub/ui` package
3. `rg -i "<name>" frontend/app/src/shared/components/`
4. `rg -i "<name>" frontend/packages/ui/src/components/`

If a primitive matches 80%+ of what you need, **wrap or extend it** instead of writing a new one. Examples:

- Need a peer picker with a paste-UUID toggle? Wrap `PeerInput` and add the toggle.
- Need a card with a custom header slot? Extend `Card`/`CardHeader` in `@infrahub/ui`, not in feature code.
- Need a single-object lookup by UUID? Use `useGetObject` — never hand-roll a `gql` string.

If you genuinely need a new primitive:

- Justify it in the PR description ("evaluated `PeerInput`, `Combobox`, `RelationshipComboboxList` — none cover X because Y").
- Add an entry to `shared-components.md` so the next person finds it.
- Place it in `shared/components/` (not in an entity) if it's reusable. Place it in `frontend/packages/ui/` if it's generic enough for any surface.

### Anti-patterns

| Anti-pattern | Replacement |
|---|---|
| `<section className="rounded-md border bg-white p-4 shadow-lg">…</section>` | `Card` from `@infrahub/ui` |
| Hand-rolled `gql` + `graphqlClient.query(...)` for a single node | `useGetObject({ objectId, objectSchema: { kind: "CoreNode" } })` |
| Reinvented kind combobox + object combobox | Wrap `PeerInput` (`shared/components/inputs/peer.tsx`) |
| Custom dialog with focus trap | `Modal` from `@infrahub/ui` |
| `<button className="bg-custom-blue-700 …">` | `Button` from `@infrahub/ui` |

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

- 3+ returns with same wrapper structure
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
