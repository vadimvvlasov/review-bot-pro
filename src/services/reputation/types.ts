import { z } from "zod";

/** Sentiment enum — mirrors SentimentEnum in the product spec (AC-11). */
export const sentimentEnum = z.enum(["positive", "neutral", "negative"]);
export type Sentiment = z.infer<typeof sentimentEnum>;

/** Review lifecycle: draft -> approved (AC-17). */
export const reviewStatusEnum = z.enum(["draft", "approved"]);
export type ReviewStatus = z.infer<typeof reviewStatusEnum>;

export const reviewSourceEnum = z.enum(["manual", "csv", "google", "yelp", "tripadvisor"]);
export type ReviewSource = z.infer<typeof reviewSourceEnum>;

/** PUT /api/settings payload. */
export const businessSettingsSchema = z.object({
  business_name: z.string().min(1).max(100),
  business_type: z.string().min(1).max(50),
  description: z.string().min(3).max(1000),
  brand_voice: z.string().min(1).max(100),
});
export type BusinessSettings = z.infer<typeof businessSettingsSchema>;

/** POST /api/reviews payload (AC-03). */
export const reviewCreateSchema = z.object({
  author_name: z.string().trim().min(1).max(100),
  review_text: z.string().trim().min(3).max(5000),
  rating: z.number().int().min(1).max(5),
  source: reviewSourceEnum.default("manual"),
});
export type ReviewCreate = z.infer<typeof reviewCreateSchema>;

/** POST /api/reviews/{id}/generate payload. */
export const generateReplySchema = z.object({
  instructions: z.string().max(500).optional(),
});
export type GenerateReplyRequest = z.infer<typeof generateReplySchema>;

/** PATCH /api/reviews/{id} payload (AC-16, AC-17). */
export const updateReviewSchema = z.object({
  reply_text: z.string().max(500).nullish(),
  status: reviewStatusEnum.optional(),
});
export type UpdateReviewRequest = z.infer<typeof updateReviewSchema>;

/** LLM structured output contract (AC-09..AC-13). */
export const llmStructuredOutputSchema = z.object({
  reply_text: z.string().min(10).max(500),
  detected_sentiment: sentimentEnum.nullish().catch(null),
  detected_tags: z.array(z.string()).catch([]),
});
export type LLMStructuredOutput = z.infer<typeof llmStructuredOutputSchema>;

export interface Review {
  id: string;
  author_name: string;
  rating: number;
  review_text: string;
  source: ReviewSource;
  reply_text: string | null;
  detected_sentiment: Sentiment | null;
  detected_tags: string[];
  status: ReviewStatus;
  created_at: string;
}

export interface ImportRowError {
  row: number;
  error: string;
}

export interface ImportSummary {
  status: "success";
  imported: number;
  skipped: number;
  errors: ImportRowError[];
}

/** Error carrying an HTTP-like status so the UI can react per the spec. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
