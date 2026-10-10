import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../services/api";
import type { CompileResult, ExampleQuery } from "../types";

interface QueryState {
  sql: string;
  setSql: (sql: string) => void;
  result: CompileResult | null;
  loading: boolean;
  error: string | null;
  examples: ExampleQuery[];
  run: (sql?: string) => Promise<void>;
  clear: () => void;
  hasResult: boolean;
}

const QueryContext = createContext<QueryState | undefined>(undefined);

const DEFAULT_SQL = `SELECT s.name, d.name
FROM students s
INNER JOIN departments d ON s.dept_id = d.id
WHERE s.cgpa > 8.0 AND d.name = 'CSE';`;

export function QueryProvider({ children }: { children: ReactNode }) {
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [result, setResult] = useState<CompileResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [examples, setExamples] = useState<ExampleQuery[]>([]);

  useEffect(() => {
    api
      .examples()
      .then(setExamples)
      .catch(() => setExamples([]));
  }, []);

  const run = useCallback(
    async (override?: string) => {
      const query = override ?? sql;
      setLoading(true);
      setError(null);
      try {
        const response = await api.optimize(query);
        setResult(response);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to reach the queryX backend. Is it running on port 8000?",
        );
        setResult(null);
      } finally {
        setLoading(false);
      }
    },
    [sql],
  );

  const clear = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  const value = useMemo<QueryState>(
    () => ({
      sql,
      setSql,
      result,
      loading,
      error,
      examples,
      run,
      clear,
      hasResult: result !== null,
    }),
    [sql, result, loading, error, examples, run, clear],
  );

  return <QueryContext.Provider value={value}>{children}</QueryContext.Provider>;
}

export function useQuery(): QueryState {
  const context = useContext(QueryContext);
  if (!context) {
    throw new Error("useQuery must be used within a QueryProvider");
  }
  return context;
}
