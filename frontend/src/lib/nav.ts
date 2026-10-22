export interface NavItem {
  id: string;
  label: string;
  hint: string;
  isNew?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "editor", label: "Query Editor", hint: "Write SQL and run the pipeline" },
  { id: "bytecode", label: "Bytecode & VM", hint: "Code generation & execution", isNew: true },
  { id: "tokens", label: "Tokens", hint: "Lexer output" },
  { id: "ast", label: "AST", hint: "Abstract syntax tree" },
  { id: "ir", label: "Relational IR", hint: "Logical algebra" },
  { id: "optimization", label: "Optimization", hint: "Rule-based rewrites" },
  { id: "plans", label: "Query Plans", hint: "Physical plans & costs" },
];
