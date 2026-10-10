import { TreeGraph, type GraphNode } from "../../components/TreeGraph";
import { opTone } from "../../components/Badge";
import { formatCost, formatNumber } from "../../lib/format";
import type { PhysicalPlanNode } from "../../types";

let counter = 0;

function toGraph(node: PhysicalPlanNode, prefix: string): GraphNode {
  counter += 1;
  return {
    id: `${prefix}-${counter}`,
    label: node.label,
    sublabel: `rows ${formatNumber(node.estimatedRows)} · cost ${formatCost(node.estimatedCost)}`,
    tone: opTone(node.op),
    children: node.children.map((child) => toGraph(child, prefix)),
  };
}

export function PlanTree({ plan, height = 420 }: { plan: PhysicalPlanNode; height?: number }) {
  counter = 0;
  return <TreeGraph root={toGraph(plan, plan.op)} height={height} />;
}
