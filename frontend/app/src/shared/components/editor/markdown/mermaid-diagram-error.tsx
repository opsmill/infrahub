interface MermaidDiagramErrorProps {
  message: string;
  code: string;
}

export function MermaidDiagramError({ message, code }: MermaidDiagramErrorProps) {
  return (
    <div>
      <div className="whitespace-pre-wrap rounded-md bg-danger-surface p-2 font-mono text-danger text-sm">
        {message}
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  );
}
