import { afterEach, describe, expect, it, vi } from "vitest";
import { createHttpReputationService } from "./http-service";
import { ApiError } from "./types";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === null ? "" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("http-service (FastAPI contract)", () => {
  it("GET /settings returns the profile object", async () => {
    const profile = {
      business_name: "Daily Grind Cafe",
      business_type: "Coffee Shop",
      description: "Cozy local cafe.",
      brand_voice: "warm",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, profile)),
    );
    const service = createHttpReputationService();
    expect(await service.getSettings()).toEqual(profile);
    expect(fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/settings$/), undefined);
  });

  it("GET /settings maps 404 to null (no profile yet)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(404, { message: "Not found" })),
    );
    expect(await createHttpReputationService().getSettings()).toBeNull();
  });

  it("POST /reviews sends JSON and returns the created draft", async () => {
    const created = { id: "r1", status: "draft" };
    const fetchMock = vi.fn(async () => jsonResponse(201, created));
    vi.stubGlobal("fetch", fetchMock);
    const payload = { author_name: "Ann", review_text: "Great espresso.", rating: 4 };
    expect(await createHttpReputationService().createReview(payload)).toEqual(created);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/reviews$/);
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init?.body as string)).toMatchObject({ author_name: "Ann" });
  });

  it("generateReply omits the body when instructions are empty", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { id: "r1" }));
    vi.stubGlobal("fetch", fetchMock);
    await createHttpReputationService().generateReply("r1");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/reviews\/r1\/generate$/);
    expect(init?.method).toBe("POST");
    expect(init?.body).toBeUndefined();
  });

  it("generateReply forwards steering instructions and maps 500 to ApiError", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { id: "r1" }));
    vi.stubGlobal("fetch", fetchMock);
    await createHttpReputationService().generateReply("r1", { instructions: "be brief" });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init?.body as string)).toEqual({ instructions: "be brief" });

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(500, { message: "Groq request failed: timed out" })),
    );
    const error = await createHttpReputationService()
      .generateReply("r1")
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
    expect((error as ApiError).message).toContain("timed out");
  });

  it("DELETE resolves void on 204 and import posts multipart form", async () => {
    const fetchMock = vi.fn(async (url: string) =>
      String(url).endsWith("/import")
        ? jsonResponse(201, { status: "success", imported: 1, skipped: 0, errors: [] })
        : new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const service = createHttpReputationService();
    await expect(service.deleteReview("r1")).resolves.toBeUndefined();
    const summary = await service.importReviewsCsv({
      name: "r.csv",
      size: 42,
      text: "author_name,review_text,rating\nAnn,Great espresso.,5",
    });
    expect(summary).toEqual({ status: "success", imported: 1, skipped: 0, errors: [] });
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(init?.body).toBeInstanceOf(FormData);
  });
});
