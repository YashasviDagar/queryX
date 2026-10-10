import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CandidatePlan } from "../../types";
import { PlanCard } from "./PlanCard";

vi.mock("./PlanTree", () => ({
  PlanTree: () => <div data-testid="plan-tree" />,
}));

const basePlan: CandidatePlan = {
  id: "plan-b",
  name: "Plan B",
  description: "Hash join over index scans",
  joinOrder: ["students", "departments"],
  joinAlgorithm: "HashJoin",
  accessPaths: ["IndexScan(students)"],
  estimatedCost: 1234.5,
  estimatedRows: 120,
  estimatedMemory: 2048,
  estimatedOperations: 5000,
  selected: false,
  tree: {
    op: "Scan",
    label: "SCAN students",
    details: {},
    estimatedRows: 120,
    estimatedCost: 1234.5,
    estimatedMemory: 0,
    estimatedOperations: 0,
    children: [],
  },
};

describe("PlanCard", () => {
  it("shows the plan name, description and rank", () => {
    render(<PlanCard plan={basePlan} rank={1} maxCost={2000} />);

    expect(screen.getByText("Plan B")).toBeInTheDocument();
    expect(screen.getByText("Hash join over index scans")).toBeInTheDocument();
    expect(screen.getByText("rank #2")).toBeInTheDocument();
    expect(screen.queryByText("Selected")).not.toBeInTheDocument();
  });

  it("marks the selected plan and opens its tree by default", () => {
    render(
      <PlanCard plan={{ ...basePlan, selected: true }} rank={0} maxCost={2000} />,
    );

    expect(screen.getByText("Selected")).toBeInTheDocument();
    expect(screen.getByTestId("plan-tree")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide physical plan" })).toBeInTheDocument();
  });

  it("toggles the physical plan tree", () => {
    render(<PlanCard plan={basePlan} rank={1} maxCost={2000} />);

    expect(screen.queryByTestId("plan-tree")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show physical plan" }));
    expect(screen.getByTestId("plan-tree")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hide physical plan" }));
    expect(screen.queryByTestId("plan-tree")).not.toBeInTheDocument();
  });

  it("labels the cheapest non-selected plan", () => {
    render(<PlanCard plan={basePlan} rank={0} maxCost={2000} />);

    expect(screen.getByText("Cheapest")).toBeInTheDocument();
  });
});
