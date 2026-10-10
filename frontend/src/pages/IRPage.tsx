import { useState } from "react";
import { Card } from "../components/Card";
import { CodeBlock } from "../components/CodeBlock";
import { EmptyState } from "../components/States";
import { Tabs } from "../components/Tabs";
import { TreeGraph, type GraphNode } from "../components/TreeGraph";
import { opTone } from "../components/Badge";
import { useQuery } from "../store/QueryProvider";
import type { IRNode } from "../types";

let counter = 0;

function toGraph(node: IRNode): GraphNode {
  counter += 1;
  return {
    id: `${node.op}-${counter}`,
    label: node.label,
    sublabel: `${node.op} · ${node.outputColumns.length} col(s)`,
    tone: opTone(node.op),
    children: node.children.map(toGraph),
  };
}

export function IRPage() {
  const { result } = useQuery();
  const [tab, setTab] = useState("original");
  const [mode, setMode] = useState("graph");

  if (!result || !result.relationalIR) {
    return (
      <EmptyState
        title="No relational IR yet"
        description="The intermediate representation is produced after successful semantic analysis."
      />
    );
  }

  const ir = tab === "original" ? result.relationalIR : result.optimizedIR;
  const irText =
    tab === "original" ? result.relationalIRText : result.optimizedIRText;

  counter = 0;

  return (
    <Card
      title="Relational algebra IR"
      subtitle="SCAN / FILTER / PROJECT / JOIN / AGGREGATE / SORT / LIMIT"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <Tabs
            items={[
              { id: "original", label: "Original" },
              { id: "optimized", label: "Optimized" },
            ]}
            active={tab}
            onChange={setTab}
          />
          <Tabs
            items={[
              { id: "graph", label: "Graph" },
              { id: "text", label: "Text" },
            ]}
            active={mode}
            onChange={setMode}
          />
        </div>
      }
    >
      {!ir ? (
        <EmptyState title="No IR available for this view" />
      ) : mode === "graph" ? (
        <TreeGraph root={toGraph(ir)} height={520} />
      ) : (
        <CodeBlock code={irText ?? ""} maxHeight="max-h-[560px]" />
      )}
    </Card>
  );
}
