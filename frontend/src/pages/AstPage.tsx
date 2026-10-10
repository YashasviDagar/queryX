import { useState } from "react";
import { Card } from "../components/Card";
import { CodeBlock } from "../components/CodeBlock";
import { EmptyState } from "../components/States";
import { Tabs } from "../components/Tabs";
import { AstGraph } from "../features/ast/AstGraph";
import { useQuery } from "../store/QueryProvider";

export function AstPage() {
  const { result } = useQuery();
  const [view, setView] = useState("graph");

  if (!result) {
    return (
      <EmptyState
        title="No syntax tree yet"
        description="Run a query from the editor to build the AST."
      />
    );
  }
  if (!result.ast) {
    return (
      <EmptyState
        title="The query did not parse"
        description="Fix the lexical or syntax errors shown in the editor, then run again."
      />
    );
  }

  return (
    <Card
      title="Abstract syntax tree"
      subtitle="Interactive graph of the parsed query"
      actions={
        <Tabs
          items={[
            { id: "graph", label: "Graph" },
            { id: "json", label: "JSON" },
          ]}
          active={view}
          onChange={setView}
        />
      }
    >
      {view === "graph" ? (
        <AstGraph ast={result.ast} />
      ) : (
        <CodeBlock code={JSON.stringify(result.ast, null, 2)} maxHeight="max-h-[560px]" />
      )}
    </Card>
  );
}
