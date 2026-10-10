import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import type { CompileResult } from "../types";

const optimize = vi.fn();
const examples = vi.fn();

vi.mock("../services/api", () => ({
  api: {
    optimize: (sql: string) => optimize(sql),
    examples: () => examples(),
  },
}));

// Imported after the mock so the provider picks up the mocked api.
const { QueryProvider, useQuery } = await import("./QueryProvider");

function wrapper({ children }: { children: ReactNode }) {
  return <QueryProvider>{children}</QueryProvider>;
}

const fakeResult = { success: true, query: "SELECT 1" } as unknown as CompileResult;

describe("QueryProvider", () => {
  it("throws when useQuery is used outside the provider", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useQuery())).toThrow(
      "useQuery must be used within a QueryProvider",
    );
    spy.mockRestore();
  });

  it("loads examples on mount and starts with no result", async () => {
    examples.mockResolvedValue([{ id: "a", title: "A", description: "", sql: "SELECT 1" }]);
    const { result } = renderHook(() => useQuery(), { wrapper });

    await waitFor(() => expect(result.current.examples).toHaveLength(1));
    expect(result.current.hasResult).toBe(false);
    expect(result.current.sql).toContain("FROM students s");
  });

  it("stores the optimize result after run()", async () => {
    examples.mockResolvedValue([]);
    optimize.mockResolvedValue(fakeResult);
    const { result } = renderHook(() => useQuery(), { wrapper });

    await act(async () => {
      await result.current.run("SELECT 1");
    });

    expect(optimize).toHaveBeenCalledWith("SELECT 1");
    expect(result.current.result).toEqual(fakeResult);
    expect(result.current.hasResult).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("surfaces an error and clears the result when the request fails", async () => {
    examples.mockResolvedValue([]);
    optimize.mockRejectedValue(new Error("Request failed (500): boom"));
    const { result } = renderHook(() => useQuery(), { wrapper });

    await act(async () => {
      await result.current.run("SELECT 1");
    });

    expect(result.current.error).toBe("Request failed (500): boom");
    expect(result.current.result).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("clear() drops the result and error", async () => {
    examples.mockResolvedValue([]);
    optimize.mockResolvedValue(fakeResult);
    const { result } = renderHook(() => useQuery(), { wrapper });

    await act(async () => {
      await result.current.run("SELECT 1");
    });
    act(() => result.current.clear());

    expect(result.current.hasResult).toBe(false);
    expect(result.current.error).toBeNull();
  });
});
