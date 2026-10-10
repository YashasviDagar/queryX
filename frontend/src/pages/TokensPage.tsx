import { Card } from "../components/Card";
import { EmptyState } from "../components/States";
import { TokenTable } from "../features/lexer/TokenTable";
import { useQuery } from "../store/QueryProvider";

export function TokensPage() {
  const { result } = useQuery();
  if (!result) {
    return (
      <EmptyState
        title="No token stream yet"
        description="Run a query from the editor to see the lexer output."
      />
    );
  }
  return (
    <Card
      title="Token stream"
      subtitle="Every token with its type, lexeme and 1-based source position"
    >
      <TokenTable tokens={result.tokens} />
    </Card>
  );
}
