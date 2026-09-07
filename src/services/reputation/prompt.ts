import type { BusinessSettings, Review } from "./types";

/**
 * Composes the LLM system prompt from the reusable business profile.
 * Unit-tested per the spec's "System Prompt Composition" requirement.
 */
export function composeSystemPrompt(settings: BusinessSettings): string {
  return [
    `You are the owner of "${settings.business_name}", a ${settings.business_type}.`,
    `Business context: ${settings.description}`,
    `Brand voice: ${settings.brand_voice}.`,
    "Reply to the customer review in 1-3 sentences, under 500 characters.",
    "Return JSON with keys reply_text, detected_sentiment (positive|neutral|negative) and detected_tags (1-3 short lowercase keywords).",
  ].join("\n");
}

export function composeUserPrompt(
  review: Pick<Review, "author_name" | "rating" | "review_text" | "reply_text">,
  instructions?: string,
): string {
  const parts = [
    `Review by ${review.author_name} (${review.rating}/5): ${review.review_text}`,
  ];
  if (review.reply_text) parts.push(`Existing draft: ${review.reply_text}`);
  if (instructions?.trim()) parts.push(`Owner instructions: ${instructions.trim()}`);
  return parts.join("\n");
}
