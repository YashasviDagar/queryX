import { Card } from "../components/Card";
import { CodeBlock } from "../components/CodeBlock";
import { EmptyState } from "../components/States";
import { Tabs } from "../components/Tabs";
import { useState } from "react";
import { OptimizationTimeline } from "../features/optimizer/OptimizationTimeline";
import { ExplanationPanel } from "../features/explainability/ExplanationPanel";
import { useQuery } from "../store/QueryProvider";

export function OptimizationPage() {
  const { result } = useQuery();
  const [tab, setTab] = useState("timeline");

  if (!result || !result.relationalIR) {
    return (
      <EmptyState
        title="No optimization steps yet"
        description="Run a valid query to see the rule-based rewrites."
      />
    );
  }

  return (
    <div className="space-y-4">
      <Tabs
        items={[
          { id: "timeline", label: "Timeline", count: result.optimizationSteps.length },
          { id: "explain", label: "Explanations" },
          { id: "plans", label: "Before / After" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "timeline" && (
        <Card
          title="Optimization timeline"
          subtitle={`${result.optimizationSteps.length} rewrite(s) applied to the logical plan`}
        >
          <OptimizationTimeline steps={result.optimizationSteps} />
        </Card>
      )}

      {tab === "explain" && result.explanation && (
        <ExplanationPanel explanation={result.explanation} />
      )}

      {tab === "plans" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Original logical plan" subtitle="Before optimization">
            <CodeBlock code={result.relationalIRText ?? ""} maxHeight="max-h-96" />
          </Card>
          <Card title="Optimized logical plan" subtitle="After all rules">
            <CodeBlock code={result.optimizedIRText ?? ""} maxHeight="max-h-96" />
          </Card>
        </div>
      )}
    </div>
  );
}
