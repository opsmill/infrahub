interface MermaidDiagramErrorProps {
  message: string;
  source: string;
}

export function MermaidDiagramError({ message, source }: MermaidDiagramErrorProps) {
  return (
    <div>
      <div className="whitespace-pre-wrap rounded-md bg-danger-surface p-2 font-mono text-danger text-sm">
        {message}
      </div>
      <pre>
        <code>{source}</code>
      </pre>
    </div>
  );
}
