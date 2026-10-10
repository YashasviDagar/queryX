import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  type Edge,
  type Node,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";
import { Badge, opTone } from "./Badge";
import { cn } from "../lib/format";

export interface GraphNode {
  id: string;
  label: string;
  sublabel?: string;
  tone?: string;
  children: GraphNode[];
}

const NODE_WIDTH = 210;
const X_GAP = 235;
const Y_GAP = 120;

function layout(root: GraphNode): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let leaf = 0;

  function place(node: GraphNode, depth: number): { x: number; y: number } {
    let x: number;
    const y = depth * Y_GAP;
    if (!node.children.length) {
      x = leaf * X_GAP;
      leaf += 1;
    } else {
      const positions = node.children.map((child) => {
        const position = place(child, depth + 1);
        edges.push({
          id: `${node.id}->${child.id}`,
          source: node.id,
          target: child.id,
          type: "smoothstep",
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
          style: { stroke: "#737373" },
        });
        return position;
      });
      x = (positions[0].x + positions[positions.length - 1].x) / 2;
    }
    nodes.push({
      id: node.id,
      type: "queryx",
      position: { x, y },
      data: { label: node.label, sublabel: node.sublabel, tone: node.tone },
      style: { width: NODE_WIDTH },
    });
    return { x, y };
  }

  place(root, 0);
  return { nodes, edges };
}

function QueryXNode({ data }: NodeProps<{ label: string; sublabel?: string; tone?: string }>) {
  const tone = (data.tone as ReturnType<typeof opTone>) ?? "default";
  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-center shadow-sm",
        tone === "blue" && "border-blue-300 bg-blue-50 dark:border-blue-500/40 dark:bg-blue-500/10",
        tone === "purple" && "border-violet-300 bg-violet-50 dark:border-violet-500/40 dark:bg-violet-500/10",
        tone === "amber" && "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10",
        tone === "green" && "border-emerald-300 bg-emerald-50 dark:border-emerald-500/40 dark:bg-emerald-500/10",
        tone === "slate" && "border-slate-300 bg-slate-50 dark:border-slate-600 dark:bg-slate-800/60",
        tone === "default" && "border-slate-300 bg-white dark:border-slate-700 dark:bg-slate-900",
      )}
    >
      <div className="truncate font-mono text-xs font-semibold text-slate-800 dark:text-slate-100">
        {data.label}
      </div>
      {data.sublabel && (
        <div className="mt-0.5 truncate text-[11px] text-slate-500 dark:text-slate-400">
          {data.sublabel}
        </div>
      )}
    </div>
  );
}

const nodeTypes = { queryx: QueryXNode };

export function TreeGraph({ root, height = 460 }: { root: GraphNode; height?: number }) {
  const { nodes, edges } = useMemo(() => layout(root), [root]);
  return (
    <div style={{ height }} className="rounded-lg border border-slate-200 dark:border-slate-800">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.2}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
      >
        <Background color="#a3a3a3" gap={20} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
