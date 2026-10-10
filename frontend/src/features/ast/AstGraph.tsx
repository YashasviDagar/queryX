import { TreeGraph, type GraphNode } from "../../components/TreeGraph";
import type { AstNode } from "../../types";

let counter = 0;

function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}-${counter}`;
}

function describe(node: AstNode): { label: string; sublabel?: string; tone?: string } {
  switch (node.kind) {
    case "Query":
      return { label: "Query", tone: "purple" };
    case "Select":
      return {
        label: "SELECT" + (node.distinct ? " DISTINCT" : ""),
        tone: "blue",
      };
    case "From":
      return { label: "FROM", tone: "blue" };
    case "Join":
      return { label: `JOIN (${String(node.joinType)})`, tone: "purple" };
    case "Where":
      return { label: "WHERE", tone: "amber" };
    case "GroupBy":
      return { label: "GROUP BY", tone: "green" };
    case "OrderBy":
      return { label: "ORDER BY", tone: "slate" };
    case "OrderByItem":
      return { label: `ORDER ${String(node.direction)}`, tone: "slate" };
    case "Limit":
      return { label: `LIMIT ${String(node.count)}`, tone: "slate" };
    case "Column": {
      const table = node.table ? `${String(node.table)}.` : "";
      const alias = node.alias ? ` AS ${(node.alias as AstNode).name}` : "";
      return { label: `${table}${String(node.name)}${alias}`, sublabel: "Column", tone: "green" };
    }
    case "Table": {
      const alias = node.alias ? ` AS ${(node.alias as AstNode).name}` : "";
      return { label: `${String(node.name)}${alias}`, sublabel: "Table", tone: "blue" };
    }
    case "Alias":
      return { label: String(node.name), sublabel: "Alias", tone: "slate" };
    case "FunctionCall": {
      const inner = node.star
        ? "*"
        : ((node.args as AstNode[]) ?? []).map((arg) => arg.kind).join(", ");
      return { label: `${String(node.name)}(${inner})`, sublabel: "FunctionCall", tone: "amber" };
    }
    case "Literal":
      return { label: String(node.value), sublabel: String(node.literalType), tone: "amber" };
    case "Comparison":
    case "BinaryExpression":
    case "LogicalExpression":
      return { label: String(node.operator), sublabel: node.kind, tone: "purple" };
    default:
      return { label: node.kind };
  }
}

function childrenOf(node: AstNode): AstNode[] {
  switch (node.kind) {
    case "Query": {
      const list: AstNode[] = [];
      if (node.select) list.push(node.select as AstNode);
      if (node.from) list.push(node.from as AstNode);
      for (const join of (node.joins as AstNode[]) ?? []) list.push(join);
      if (node.where) list.push(node.where as AstNode);
      if (node.groupBy) list.push(node.groupBy as AstNode);
      if (node.orderBy) list.push(node.orderBy as AstNode);
      if (node.limit) list.push(node.limit as AstNode);
      return list;
    }
    case "Select":
      return (node.columns as AstNode[]) ?? [];
    case "From":
      return node.table ? [node.table as AstNode] : [];
    case "Join":
      return [node.table as AstNode, node.condition as AstNode].filter(Boolean);
    case "Where":
      return node.condition ? [node.condition as AstNode] : [];
    case "GroupBy":
      return (node.columns as AstNode[]) ?? [];
    case "OrderBy":
      return (node.items as AstNode[]) ?? [];
    case "OrderByItem":
      return node.column ? [node.column as AstNode] : [];
    case "Comparison":
    case "BinaryExpression":
    case "LogicalExpression":
      return [node.left as AstNode, node.right as AstNode].filter(Boolean);
    case "FunctionCall":
      return (node.args as AstNode[]) ?? [];
    default:
      return [];
  }
}

export function astToGraph(node: AstNode): GraphNode {
  const description = describe(node);
  return {
    id: nextId(node.kind),
    label: description.label,
    sublabel: description.sublabel,
    tone: description.tone,
    children: childrenOf(node).map(astToGraph),
  };
}

export function AstGraph({ ast }: { ast: AstNode }) {
  counter = 0;
  return <TreeGraph root={astToGraph(ast)} height={520} />;
}
