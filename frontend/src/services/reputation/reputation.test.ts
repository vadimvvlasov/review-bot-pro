import { describe, expect, it } from "vitest";
import { CSV_MAX_ROWS, parseReviewCsv, splitCsvLine } from "./csv";
import { composeSystemPrompt, composeUserPrompt } from "./prompt";
import { createMockReputationService, mockLlmCall } from "./mock-service";
import {
  ApiError,
  businessSettingsSchema,
  llmStructuredOutputSchema,
  reviewCreateSchema,
  type BusinessSettings,
} from "./types";

const settings: BusinessSettings = {
  business_name: "Daily Grind Cafe",
  business_type: "Coffee Shop",
  description: "Cozy local cafe serving organic brews.",
  brand_voice: "warm and playful",
};

const service = () => createMockReputationService({ latency: 0, seed: false });

const csv = (rows: string[]) => ["author_name,review_text,rating", ...rows].join("\n");

describe("input schema validation (AC-03)", () => {
  it("rejects ratings outside 1-5", () => {
    for (const rating of [0, 6, 2.5]) {
      expect(
        reviewCreateSchema.safeParse({ author_name: "A", review_text: "Nice", rating }).success,
      ).toBe(false);
    }
  });

  it("rejects review text under 3 characters and names over 100", () => {
    expect(reviewCreateSchema.safeParse({ author_name: "A", review_text: "ok", rating: 4 }).success).toBe(false);
    expect(
      reviewCreateSchema.safeParse({ author_name: "x".repeat(101), review_text: "Nice", rating: 4 })
        .success,
    ).toBe(false);
  });

  it("accepts a valid review and defaults the source to manual", () => {
    const parsed = reviewCreateSchema.parse({
      author_name: "John Doe",
      review_text: "Great espresso but service was slow.",
      rating: 4,
    });
    expect(parsed.source).toBe("manual");
  });

  it("validates business settings bounds", () => {
    expect(businessSettingsSchema.safeParse(settings).success).toBe(true);
    expect(businessSettingsSchema.safeParse({ ...settings, description: "no" }).success).toBe(false);
  });
});

describe("CSV parser edge cases (AC-04..AC-06)", () => {
  it("handles quoted fields containing commas and escaped quotes", () => {
    expect(splitCsvLine('Ann,"Loved it, truly ""great""",5')).toEqual([
      "Ann",
      'Loved it, truly "great"',
      "5",
    ]);
  });

  it("throws on an empty file and on malformed headers", () => {
    expect(() => parseReviewCsv("")).toThrow(/empty/i);
    expect(() => parseReviewCsv("name,text,stars\nAnn,Nice,5")).toThrow(/missing required column/i);
  });

  it("throws when the row count exceeds the limit", () => {
    const rows = Array.from({ length: CSV_MAX_ROWS + 1 }, (_, i) => `User ${i},Solid coffee here,5`);
    expect(() => parseReviewCsv(csv(rows))).toThrow(/limit is 100/);
  });

  it("throws when the file exceeds 1 MB", () => {
    const big = csv([`Ann,${"a".repeat(1024 * 1024)},5`]);
    expect(() => parseReviewCsv(big)).toThrow(/1 MB/);
  });

  it("keeps valid rows and reports invalid ones with row numbers", () => {
    const result = parseReviewCsv(
      csv([
        "Ann,Great espresso and fast service,5",
        ",Empty author name here,4",
        "Bob,Nice spot for work,9",
        "Cara,Lovely pastries every morning,4",
      ]),
    );
    expect(result.valid).toHaveLength(2);
    expect(result.errors).toEqual([
      { row: 3, error: "Author name cannot be empty" },
      { row: 4, error: "Rating must be between 1 and 5" },
    ]);
  });
});

describe("LLM structured output fallbacks (AC-11..AC-13)", () => {
  it("degrades an invalid sentiment to null and bad tags to an empty list", () => {
    const parsed = llmStructuredOutputSchema.parse({
      reply_text: "Thanks so much for the kind words, we hope to see you soon!",
      detected_sentiment: "furious",
      detected_tags: [1, 2],
    });
    expect(parsed.detected_sentiment).toBeNull();
    expect(parsed.detected_tags).toEqual([]);
  });

  it("rejects replies longer than 500 characters", () => {
    expect(
      llmStructuredOutputSchema.safeParse({ reply_text: "x".repeat(501), detected_tags: [] })
        .success,
    ).toBe(false);
  });
});

describe("system prompt composition", () => {
  it("injects every business profile field", () => {
    const prompt = composeSystemPrompt(settings);
    expect(prompt).toContain("Daily Grind Cafe");
    expect(prompt).toContain("Coffee Shop");
    expect(prompt).toContain("Cozy local cafe serving organic brews.");
    expect(prompt).toContain("warm and playful");
  });

  it("includes the existing draft and steering instructions when regenerating", () => {
    const prompt = composeUserPrompt(
      { author_name: "Ann", rating: 2, review_text: "Slow service", reply_text: "Sorry!" },
      "be more empathetic",
    );
    expect(prompt).toContain("Ann");
    expect(prompt).toContain("Existing draft: Sorry!");
    expect(prompt).toContain("Owner instructions: be more empathetic");
  });
});

describe("mock reply generation (AC-09, AC-10, AC-12)", () => {
  it("stays under 500 characters and returns bounded metadata", () => {
    const output = mockLlmCall({
      settings,
      review: {
        author_name: "Tom Ridley",
        rating: 2,
        review_text: "Waited 20 minutes and the latte was lukewarm; the service needs work.",
        reply_text: null,
      },
    });
    expect(output.reply_text.length).toBeLessThanOrEqual(500);
    expect(output.detected_sentiment).toBe("negative");
    expect(output.detected_tags.length).toBeGreaterThan(0);
    expect(output.detected_tags.length).toBeLessThanOrEqual(3);
  });

  it("classifies a glowing review as positive", () => {
    const output = mockLlmCall({
      settings,
      review: {
        author_name: "Maria",
        rating: 5,
        review_text: "Best flat white in town and lovely friendly staff.",
        reply_text: null,
      },
    });
    expect(output.detected_sentiment).toBe("positive");
  });
});

describe("settings persistence (AC-01, AC-02)", () => {
  it("saves and reads back the exact payload", async () => {
    const api = service();
    await api.saveSettings(settings);
    await expect(api.getSettings()).resolves.toEqual(settings);
  });
});

describe("review lifecycle through the service layer", () => {
  const review = {
    author_name: "Ann Lee",
    review_text: "Great espresso but service was a bit slow today.",
    rating: 4 as const,
    source: "manual" as const,
  };

  it("creates drafts with empty AI fields (AC-07)", async () => {
    const api = service();
    const created = await api.createReview(review);
    expect(created).toMatchObject({
      status: "draft",
      reply_text: null,
      detected_sentiment: null,
      detected_tags: [],
    });
  });

  it("rejects a duplicate manual review with 409 (AC-08)", async () => {
    const api = service();
    await api.createReview(review);
    await expect(api.createReview(review)).rejects.toMatchObject({ status: 409 });
  });

  it("skips duplicates on CSV import and reports partial results (AC-06)", async () => {
    const api = service();
    const text = csv([
      "Ann,Great espresso and fast service,5",
      "Bob,Nice spot for work,4",
      "Bob,Nice spot for work,4",
      "Cara,Bad,9",
    ]);
    const summary = await api.importReviewsCsv({ name: "r.csv", size: text.length, text });
    expect(summary.imported).toBe(2);
    expect(summary.errors.length).toBe(summary.skipped);
    expect(await api.listReviews()).toHaveLength(2);
  });

  it("rejects an oversized CSV upload with 400 (AC-04)", async () => {
    const api = service();
    await expect(
      api.importReviewsCsv({ name: "big.csv", size: 2 * 1024 * 1024, text: csv([]) }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("overwrites the draft on regeneration without adding rows (AC-15)", async () => {
    const api = service();
    const created = await api.createReview(review);
    const first = await api.generateReply(created.id);
    const second = await api.generateReply(created.id, { instructions: "offer a free cookie" });
    expect(second.reply_text).not.toEqual(first.reply_text);
    expect(second.reply_text).toContain("free cookie");
    expect(await api.listReviews()).toHaveLength(1);
  });

  it("returns a 500-style error when the reply engine fails (AC-14)", async () => {
    const api = createMockReputationService({ latency: 0, seed: false, failGeneration: true });
    const created = await api.createReview(review);
    await expect(api.generateReply(created.id)).rejects.toMatchObject({ status: 500 });
  });

  it("approves a review in one transition (AC-17)", async () => {
    const api = service();
    const created = await api.createReview(review);
    await api.generateReply(created.id);
    const approved = await api.updateReview(created.id, {
      reply_text: "Thanks Ann, we are on it!",
      status: "approved",
    });
    expect(approved).toMatchObject({ status: "approved", reply_text: "Thanks Ann, we are on it!" });
    const stored = (await api.listReviews()).find((r) => r.id === created.id);
    expect(stored?.status).toBe("approved");
  });

  it("404s on unknown ids", async () => {
    const api = service();
    await expect(api.generateReply("nope")).rejects.toMatchObject({ status: 404 });
    await expect(api.deleteReview("nope")).rejects.toMatchObject({ status: 404 });
  });
});
