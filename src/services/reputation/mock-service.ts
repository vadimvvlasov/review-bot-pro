import { CSV_MAX_BYTES, parseReviewCsv } from "./csv";
import { composeSystemPrompt, composeUserPrompt } from "./prompt";
import {
  ApiError,
  llmStructuredOutputSchema,
  type BusinessSettings,
  type GenerateReplyRequest,
  type ImportSummary,
  type Review,
  type ReviewCreate,
  type Sentiment,
  type UpdateReviewRequest,
} from "./types";
import type { ReputationService } from "./service";

const DEFAULT_SETTINGS: BusinessSettings = {
  business_name: "Daily Grind Cafe",
  business_type: "Coffee Shop",
  description: "Cozy local cafe serving organic single-origin brews and homemade pastries.",
  brand_voice: "warm, welcoming, and slightly playful",
};

const SEED: Array<Omit<Review, "id">> = [
  {
    author_name: "Maria Petrova",
    rating: 5,
    review_text:
      "The flat white here is the best in town and the staff remembered my name on my second visit. The pastries are always fresh.",
    source: "google",
    reply_text: null,
    detected_sentiment: null,
    detected_tags: [],
    status: "draft",
    created_at: "2026-09-05T08:12:00.000Z",
  },
  {
    author_name: "Tom Ridley",
    rating: 2,
    review_text:
      "Waited 20 minutes for a latte during the morning rush and it arrived lukewarm. Nice place, but the service needs work.",
    source: "yelp",
    reply_text: null,
    detected_sentiment: null,
    detected_tags: [],
    status: "draft",
    created_at: "2026-09-04T15:40:00.000Z",
  },
  {
    author_name: "Aiko Tanaka",
    rating: 4,
    review_text:
      "Lovely spot to work from in the afternoon. Wifi is fast, though the pricing on cold brew feels a touch high.",
    source: "tripadvisor",
    reply_text: null,
    detected_sentiment: null,
    detected_tags: [],
    status: "draft",
    created_at: "2026-09-03T11:05:00.000Z",
  },
  {
    author_name: "Daniel Okafor",
    rating: 5,
    review_text: "Great espresso, friendly barista, and the cinnamon buns are unreal. Will be back weekly.",
    source: "google",
    reply_text:
      "Thank you so much, Daniel! We are thrilled the espresso and cinnamon buns hit the spot. See you next week!",
    detected_sentiment: "positive",
    detected_tags: ["espresso", "service"],
    status: "approved",
    created_at: "2026-09-01T09:22:00.000Z",
  },
];

const POSITIVE_WORDS = ["great", "best", "love", "lovely", "amazing", "friendly", "fresh", "unreal", "perfect"];
const NEGATIVE_WORDS = ["wait", "waited", "slow", "cold", "lukewarm", "rude", "dirty", "expensive", "bad"];
const TAG_WORDS: Record<string, string[]> = {
  service: ["service", "staff", "barista", "waited", "wait", "rude", "friendly"],
  pricing: ["price", "pricing", "expensive", "cheap", "value", "high"],
  coffee: ["coffee", "espresso", "latte", "brew", "flat white", "cold brew"],
  food: ["pastry", "pastries", "bun", "buns", "cake", "food", "sandwich"],
  atmosphere: ["cozy", "atmosphere", "music", "wifi", "seating", "spot", "place"],
  speed: ["slow", "fast", "quick", "minutes", "rush"],
};

function uuid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `rv-${Math.random().toString(36).slice(2, 10)}`;
}

function classify(reviewText: string, rating: number): Sentiment {
  const text = reviewText.toLowerCase();
  const pos = POSITIVE_WORDS.filter((w) => text.includes(w)).length + (rating >= 4 ? 2 : 0);
  const neg = NEGATIVE_WORDS.filter((w) => text.includes(w)).length + (rating <= 2 ? 2 : 0);
  if (pos > neg) return "positive";
  if (neg > pos) return "negative";
  return "neutral";
}

function extractTags(reviewText: string): string[] {
  const text = reviewText.toLowerCase();
  const tags = Object.entries(TAG_WORDS)
    .filter(([, words]) => words.some((w) => text.includes(w)))
    .map(([tag]) => tag);
  return tags.slice(0, 3);
}

function clampReply(text: string): string {
  const trimmed = text.trim();
  return trimmed.length <= 500 ? trimmed : `${trimmed.slice(0, 497).trimEnd()}...`;
}

/** Deterministic stand-in for the single structured LLM call (AC-09..AC-13). */
export function mockLlmCall(input: {
  settings: BusinessSettings;
  review: Pick<Review, "author_name" | "rating" | "review_text" | "reply_text">;
  instructions?: string;
}) {
  // Prompts are composed exactly as the real backend would, so the mock
  // exercises the same context-engineering code path.
  void composeSystemPrompt(input.settings);
  void composeUserPrompt(input.review, input.instructions);

  const { settings, review, instructions } = input;
  const sentiment = classify(review.review_text, review.rating);
  const firstName = review.author_name.split(" ")[0] ?? "there";
  const opening =
    sentiment === "positive"
      ? `Thank you for the kind words, ${firstName}!`
      : sentiment === "negative"
        ? `Thank you for the honest feedback, ${firstName}, and we're sorry we fell short.`
        : `Thanks for taking the time to share this, ${firstName}.`;

  const middle =
    sentiment === "negative"
      ? `We're reviewing how we handle busy periods at ${settings.business_name} so the wait and the quality both improve.`
      : `Hearing that from a guest at ${settings.business_name} genuinely makes our day.`;

  const closing = instructions?.trim()
    ? `As promised: ${instructions.trim().replace(/\s+/g, " ").slice(0, 160)}`
    : "We hope to welcome you back soon.";

  return llmStructuredOutputSchema.parse({
    reply_text: clampReply([opening, middle, closing].join(" ")),
    detected_sentiment: sentiment,
    detected_tags: extractTags(review.review_text),
  });
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface MockOptions {
  /** Artificial latency, in ms. Set to 0 in tests. */
  latency?: number;
  seed?: boolean;
  /** Force the LLM step to fail, to exercise AC-14. */
  failGeneration?: boolean;
}

export function createMockReputationService(options: MockOptions = {}): ReputationService {
  const latency = options.latency ?? 320;
  let settings: BusinessSettings | null = { ...DEFAULT_SETTINGS };
  const reviews: Review[] = (options.seed ?? true)
    ? SEED.map((r) => ({ ...r, id: uuid() }))
    : [];

  const isDuplicate = (author: string, text: string) =>
    reviews.some(
      (r) =>
        r.author_name.trim().toLowerCase() === author.trim().toLowerCase() &&
        r.review_text.trim().toLowerCase() === text.trim().toLowerCase(),
    );

  const find = (id: string) => {
    const review = reviews.find((r) => r.id === id);
    if (!review) throw new ApiError(404, "Review not found");
    return review;
  };

  return {
    async getSettings() {
      await delay(latency);
      return settings ? { ...settings } : null;
    },

    async saveSettings(payload) {
      await delay(latency);
      settings = { ...payload };
      return { ...settings };
    },

    async listReviews() {
      await delay(latency);
      return reviews
        .slice()
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map((r) => ({ ...r, detected_tags: [...r.detected_tags] }));
    },

    async createReview(payload) {
      await delay(latency);
      if (isDuplicate(payload.author_name, payload.review_text)) {
        throw new ApiError(409, "This review already exists in your queue");
      }
      const review: Review = {
        id: uuid(),
        author_name: payload.author_name,
        rating: payload.rating,
        review_text: payload.review_text,
        source: payload.source ?? "manual",
        reply_text: null,
        detected_sentiment: null,
        detected_tags: [],
        status: "draft",
        created_at: new Date().toISOString(),
      };
      reviews.push(review);
      return { ...review };
    },

    async importReviewsCsv(file) {
      await delay(latency);
      if (file.size > CSV_MAX_BYTES) {
        throw new ApiError(400, "CSV file exceeds the 1 MB size limit");
      }
      let parsed;
      try {
        parsed = parseReviewCsv(file.text);
      } catch (error) {
        throw new ApiError(400, error instanceof Error ? error.message : "Invalid CSV file");
      }

      const errors = [...parsed.errors];
      let imported = 0;
      for (const row of parsed.valid) {
        if (isDuplicate(row.author_name, row.review_text)) {
          errors.push({ row: imported + errors.length + 2, error: "Duplicate review skipped" });
          continue;
        }
        reviews.push({
          id: uuid(),
          author_name: row.author_name,
          rating: row.rating,
          review_text: row.review_text,
          source: "csv",
          reply_text: null,
          detected_sentiment: null,
          detected_tags: [],
          status: "draft",
          created_at: new Date().toISOString(),
        });
        imported += 1;
      }

      const summary: ImportSummary = {
        status: "success",
        imported,
        skipped: errors.length,
        errors,
      };
      return summary;
    },

    async generateReply(id, payload) {
      await delay(latency);
      const review = find(id);
      if (options.failGeneration) {
        throw new ApiError(500, "The reply engine is unavailable right now");
      }
      if (!settings) {
        throw new ApiError(400, "Set up your business profile before generating replies");
      }
      const output = mockLlmCall({ settings, review, instructions: payload?.instructions });
      review.reply_text = output.reply_text;
      review.detected_sentiment = output.detected_sentiment ?? null;
      review.detected_tags = output.detected_tags ?? [];
      return { ...review, detected_tags: [...review.detected_tags] };
    },

    async updateReview(id, payload) {
      await delay(latency);
      const review = find(id);
      if (payload.reply_text !== undefined) review.reply_text = payload.reply_text ?? null;
      if (payload.status) review.status = payload.status;
      return { ...review, detected_tags: [...review.detected_tags] };
    },

    async deleteReview(id) {
      await delay(latency);
      const index = reviews.findIndex((r) => r.id === id);
      if (index === -1) throw new ApiError(404, "Review not found");
      reviews.splice(index, 1);
    },
  };
}
