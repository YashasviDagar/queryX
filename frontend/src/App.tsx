import { useEffect, useState } from "react";
import { Layout } from "./components/Layout";
import { QueryProvider, useQuery } from "./store/QueryProvider";
import { ThemeProvider } from "./store/ThemeProvider";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AstPage } from "./pages/AstPage";
import { EditorPage } from "./pages/EditorPage";
import { IRPage } from "./pages/IRPage";
import { OptimizationPage } from "./pages/OptimizationPage";
import { PlansPage } from "./pages/PlansPage";
import { SchemaPage } from "./pages/SchemaPage";
import { TokensPage } from "./pages/TokensPage";

function Pages({ active, onNavigate }: { active: string; onNavigate: (id: string) => void }) {
  const { result } = useQuery();
  const [runOnLoad, setRunOnLoad] = useState(false);

  useEffect(() => {
    setRunOnLoad(true);
  }, []);

  switch (active) {
    case "tokens":
      return <TokensPage />;
    case "ast":
      return <AstPage />;
    case "ir":
      return <IRPage />;
    case "optimization":
      return <OptimizationPage />;
    case "plans":
      return <PlansPage />;
    case "analytics":
      return <AnalyticsPage />;
    case "schema":
      return <SchemaPage />;
    default:
      return <EditorPage onNavigate={onNavigate} autoRun={runOnLoad && !result} />;
  }
}

export default function App() {
  const [active, setActive] = useState("editor");
  return (
    <ThemeProvider>
      <QueryProvider>
        <Layout active={active} onNavigate={setActive}>
          <Pages active={active} onNavigate={setActive} />
        </Layout>
      </QueryProvider>
    </ThemeProvider>
  );
}
