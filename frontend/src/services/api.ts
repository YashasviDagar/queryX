import type {
  AnalyzeResult,
  CompileResult,
  ExampleQuery,
  LexResult,
  ParseResult,
  SchemaResponse,
  StatisticsResponse,
} from "../types";

const BASE_URL =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

async function post<T>(path: string, sql: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed (${response.status}): ${text}`);
  }
  return (await response.json()) as T;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export const api = {
  baseUrl: BASE_URL,
  optimize: (sql: string) => post<CompileResult>("/api/optimize", sql),
  compile: (sql: string) => post<CompileResult>("/api/compile", sql),
  lex: (sql: string) => post<LexResult>("/api/lex", sql),
  parse: (sql: string) => post<ParseResult>("/api/parse", sql),
  analyze: (sql: string) => post<AnalyzeResult>("/api/analyze", sql),
  examples: () => get<ExampleQuery[]>("/api/examples"),
  schema: () => get<SchemaResponse>("/api/schema"),
  statistics: () => get<StatisticsResponse>("/api/statistics"),
};
