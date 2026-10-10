export interface NavItem {
  id: string;
  label: string;
  hint: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "editor", label: "Query Editor", hint: "Write SQL and run the pipeline" },
  { id: "tokens", label: "Tokens", hint: "Lexer output" },
  { id: "ast", label: "AST", hint: "Abstract syntax tree" },
  { id: "ir", label: "Relational IR", hint: "Logical algebra" },
  { id: "optimization", label: "Optimization", hint: "Rule-based rewrites" },
  { id: "plans", label: "Query Plans", hint: "Physical plans & costs" },
  { id: "analytics", label: "Analytics", hint: "Cost & impact charts" },
  { id: "schema", label: "Schema & Stats", hint: "Tables, columns, indexes" },
];
