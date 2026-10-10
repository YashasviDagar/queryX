import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { OptimizationStep } from "../../types";
import { OptimizationCard } from "./OptimizationCard";

const step: OptimizationStep = {
  rule: "Predicate Pushdown",
  target: "Join",
  before: "FILTER(s.cgpa > 8.0) above JOIN",
  after: "FILTER(s.cgpa > 8.0) pushed into LEFT input",
  reason: "Predicate references only ['s'].",
  estimatedImpact: {
    metricLabel: "rows entering the join",
    estimatedRowsBefore: 100020,
    estimatedRowsAfter: 12501,
    rowReduction: 87519,
    rowReductionPercent: 87.5,
    estimatedCostBefore: 22257.45,
    estimatedCostAfter: 2382.5,
    costReduction: 19874.95,
  },
};

describe("OptimizationCard", () => {
  it("renders the rule, its step number and the reason", () => {
    render(<OptimizationCard step={step} index={0} />);

    expect(screen.getByText("Predicate Pushdown")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Predicate references only ['s'].")).toBeInTheDocument();
  });

  it("shows before and after plan text", () => {
    render(<OptimizationCard step={step} index={0} />);

    expect(screen.getByText("FILTER(s.cgpa > 8.0) above JOIN")).toBeInTheDocument();
    expect(
      screen.getByText("FILTER(s.cgpa > 8.0) pushed into LEFT input"),
    ).toBeInTheDocument();
  });

  it("uses the metric label for the first impact stat", () => {
    render(<OptimizationCard step={step} index={0} />);

    expect(screen.getByText("rows entering the join")).toBeInTheDocument();
    expect(screen.getByText("Rows after")).toBeInTheDocument();
  });

  it("falls back to 'Rows before' when no metric label is given", () => {
    const { metricLabel: _omit, ...impact } = step.estimatedImpact;
    render(
      <OptimizationCard step={{ ...step, estimatedImpact: impact }} index={2} />,
    );

    expect(screen.getByText("Rows before")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
