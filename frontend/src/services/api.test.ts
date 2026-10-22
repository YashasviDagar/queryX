import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs the SQL as JSON to the optimize endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ success: true }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await api.optimize("SELECT 1");

    expect(result).toEqual({ success: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${api.baseUrl}/api/optimize`);
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({ sql: "SELECT 1" });
    vi.unstubAllGlobals();
  });

  it("GETs examples without a body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([{ id: "x" }]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.examples()).resolves.toEqual([{ id: "x" }]);
    expect(fetchMock.mock.calls[0][0]).toBe(`${api.baseUrl}/api/examples`);
    vi.unstubAllGlobals();
  });

  it("throws with status and body text on a non-OK POST", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("bad sql", { status: 422 })),
    );

    await expect(api.lex("")).rejects.toThrow("Request failed (422): bad sql");
    vi.unstubAllGlobals();
  });

  it("throws with status on a non-OK GET", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));

    await expect(api.examples()).rejects.toThrow("Request failed (500)");
    vi.unstubAllGlobals();
  });
});
