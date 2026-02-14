# Component Patterns

> Part of: `dev/guidelines/frontend/`

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
