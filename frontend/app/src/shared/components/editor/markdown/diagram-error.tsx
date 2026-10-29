interface DiagramErrorProps {
  message: string;
  source: string;
}

export function DiagramError({ message, source }: DiagramErrorProps) {
  return (
    <div>
      <div className="mermaid-error rounded-md p-2 font-mono text-sm">{message}</div>
      <pre>
        <code>{source}</code>
      </pre>
    </div>
  );
}
