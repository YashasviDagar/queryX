// Shared TypeScript types mirroring the backend Pydantic models and JSON output.

export interface CompilerDiagnostic {
  code: string;
  message: string;
  stage: string;
  line: number;
  column: number;
  suggestion?: string | null;
  location?: { line: number; column: number };
}

export interface Token {
  type: string;
  lexeme: string;
  line: number;
  column: number;
  value?: unknown;
  category?: string;
}

export interface AstNode {
  kind: string;
  line?: number;
  [key: string]: unknown;
}

export interface OutputColumn {
  name: string;
  table?: string | null;
  dataType: string;
  source: string;
  aggregate: boolean;
}

export interface SemanticResult {
  valid: boolean;
  errors: CompilerDiagnostic[];
  outputColumns: OutputColumn[];
  scope: Record<string, string>;
  referencedTables: string[];
}

export interface IRNode {
  op: string;
  label: string;
  outputColumns: string[];
  children: IRNode[];
  [key: string]: unknown;
}

export interface EstimatedImpact {
  metricLabel?: string;
  estimatedRowsBefore: number;
  estimatedRowsAfter: number;
  rowReduction: number;
  rowReductionPercent: number;
  estimatedCostBefore: number;
  estimatedCostAfter: number;
  costReduction: number;
}

export interface OptimizationStep {
  rule: string;
  target: string;
  before: string;
  after: string;
  reason: string;
  estimatedImpact: EstimatedImpact;
}

export interface PhysicalPlanNode {
  op: string;
  label: string;
  details: Record<string, unknown>;
  estimatedRows: number;
  estimatedCost: number;
  estimatedMemory: number;
  estimatedOperations: number;
  children: PhysicalPlanNode[];
}

export interface CandidatePlan {
  id: string;
  name: string;
  description: string;
  joinOrder: string[];
  joinAlgorithm: string;
  accessPaths: string[];
  estimatedCost: number;
  estimatedRows: number;
  estimatedMemory: number;
  estimatedOperations: number;
  selected: boolean;
  tree: PhysicalPlanNode;
}

export interface CostComparisonRow {
  id: string;
  name: string;
  description: string;
  joinAlgorithm: string;
  estimatedCost: number;
  estimatedRows: number;
  estimatedMemory: number;
  estimatedOperations: number;
  selected: boolean;
}

export interface OptimizationExplanation {
  rule: string;
  target: string;
  before: string;
  after: string;
  reason: string;
  metricLabel: string;
  estimatedRowsBefore: number;
  estimatedRowsAfter: number;
  rowReduction: number;
  rowReductionPercent: number;
  estimatedCostBefore: number;
  estimatedCostAfter: number;
  costReduction: number;
  narrative: string;
}

export interface PlanSelectionExplanation {
  selectedPlan: string | null;
  selectedPlanId?: string;
  reason: string;
  estimatedCost?: number;
  estimatedRows?: number;
  estimatedMemory?: number;
  estimatedOperations?: number;
  savingsVsNextBest?: number | null;
  comparison: CostComparisonRow[];
}

export interface Explanation {
  summary: string;
  optimizationExplanations: OptimizationExplanation[];
  planSelection: PlanSelectionExplanation;
}

export interface Metrics {
  stage: string;
  totalMs: number;
  planGenerationMs?: number;
  codegenMs?: number;
  candidateCount?: number;
  rulesApplied?: number;
  rulesUsed?: string[];
}

export interface ColumnStats {
  name: string;
  dataType: string;
  distinct: number;
  nullable: boolean;
  min: number | null;
  max: number | null;
  indexed: boolean;
}

export interface IndexStats {
  name: string;
  columns: string[];
  unique: boolean;
  type: string;
}

export interface TableStats {
  name: string;
  rows: number;
  columns: ColumnStats[];
  indexes: IndexStats[];
}

export interface BytecodeLine {
  address: number;
  op: string;
  args: string;
  comment: string;
}

export interface PeepholeRuleSummary {
  rule: string;
  applications: number;
  description: string;
}

export interface PeepholeExample {
  rule: string;
  before: string[];
  after: string[];
}

export interface VmExecution {
  columns: string[];
  rows: unknown[][];
  rowCount: number;
  truncated: boolean;
  instructionsExecuted: number;
  opcodeCounts: Record<string, number>;
  elapsedMs: number;
}

export interface PlanCheck {
  id: string;
  name: string;
  description: string;
  estimatedCost: number;
  selected: boolean;
  status: "match" | "mismatch" | "skipped" | "error";
  reason?: string;
  rowCount?: number;
  instructionsExecuted?: number;
  programLength?: number;
}

export interface Codegen {
  success: boolean;
  error?: string;
  plan?: string;
  notes?: string[];
  sampleData?: { table: string; sampleRows: number; realRows: number }[];
  bytecode?: BytecodeLine[];
  bytecodeText?: string;
  unoptimizedBytecodeText?: string;
  peephole?: {
    instructionsBefore: number;
    instructionsAfter: number;
    rules: PeepholeRuleSummary[];
    examples: PeepholeExample[];
  };
  execution?: VmExecution;
  unoptimizedExecution?: { instructionsExecuted: number; elapsedMs: number; sameResult: boolean };
  planChecks?: PlanCheck[];
}

export interface CompileResult {
  success: boolean;
  query: string;
  tokens: Token[];
  ast: AstNode | null;
  semanticErrors: CompilerDiagnostic[];
  relationalIR: IRNode | null;
  relationalIRText?: string;
  optimizedIR: IRNode | null;
  optimizedIRText?: string;
  optimizationSteps: OptimizationStep[];
  candidatePlans: CandidatePlan[];
  selectedPlan: CandidatePlan | null;
  costComparison: CostComparisonRow[];
  explanation: Explanation | null;
  codegen?: Codegen | null;
  statistics?: { tables: TableStats[] };
  costConfig?: Record<string, number>;
  metrics: Metrics;
  errors: CompilerDiagnostic[];
}

export interface RandomQuery {
  sql: string;
  description: string;
}

export interface ExampleQuery {
  id: string;
  title: string;
  description: string;
  sql: string;
}

export interface LexResult {
  success: boolean;
  tokens: Token[];
  errors: CompilerDiagnostic[];
}

export interface ParseResult {
  success: boolean;
  ast: AstNode | null;
  tokens: Token[];
  errors: CompilerDiagnostic[];
}

export interface AnalyzeResult {
  success: boolean;
  ast: AstNode | null;
  semantic: SemanticResult | null;
  errors: CompilerDiagnostic[];
}

