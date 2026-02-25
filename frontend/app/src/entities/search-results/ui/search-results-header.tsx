import { Icon } from "@iconify-icon/react";
import { useEffect, useRef } from "react";

import { Badge } from "@/shared/components/ui/badge";

type SearchResultsHeaderProps = {
  query: string;
  totalCount: number;
  onQueryChange: (query: string) => void;
};

export function SearchResultsHeader({
  query,
  totalCount,
  onQueryChange,
}: SearchResultsHeaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "/" && document.activeElement !== inputRef.current) {
        event.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const value = inputRef.current?.value.trim();
    if (value !== undefined && value !== query) {
      onQueryChange(value);
    }
  }

  return (
    <header className="flex items-center gap-4 border-gray-200 border-b bg-white px-4 py-3">
      <form onSubmit={handleSubmit} className="flex grow items-center gap-2">
        <Icon icon="mdi:magnify" className="text-custom-blue-600 text-xl" />
        <input
          ref={inputRef}
          type="text"
          defaultValue={query}
          key={query}
          placeholder="Search..."
          aria-label="Search query"
          className="grow border-none bg-transparent py-1 text-lg outline-hidden"
          data-testid="search-results-input"
        />
      </form>

      <Badge variant="blue" className="shrink-0">
        {totalCount} {totalCount === 1 ? "result" : "results"}
      </Badge>
    </header>
  );
}
