import { useEffect, useState } from "react";
import { Check, Copy, Sparkles, Star, Trash2, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useDeleteReview,
  useGenerateReply,
  useUpdateReview,
} from "@/services/reputation/hooks";
import type { Review, Sentiment } from "@/services/reputation/types";

const SENTIMENT_STYLE: Record<Sentiment, string> = {
  positive: "border-transparent bg-success text-success-foreground",
  neutral: "border-transparent bg-secondary text-secondary-foreground",
  negative: "border-transparent bg-destructive text-destructive-foreground",
};

export function ReviewCard({ review }: { review: Review }) {
  const generate = useGenerateReply();
  const update = useUpdateReview();
  const remove = useDeleteReview();

  // AC-16: edits live only in local state until Approve is pressed.
  const [draft, setDraft] = useState(review.reply_text ?? "");
  const [instructions, setInstructions] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setDraft(review.reply_text ?? "");
  }, [review.reply_text]);

  function runGenerate() {
    setFailed(false);
    generate.mutate(
      { id: review.id, payload: instructions.trim() ? { instructions } : undefined },
      {
        onSuccess: (updated) => {
          setDraft(updated.reply_text ?? "");
          setInstructions("");
        },
        onError: () => {
          setFailed(true);
          toast.error("The reply engine didn't respond");
        },
      },
    );
  }

  function approve() {
    update.mutate(
      { id: review.id, payload: { reply_text: draft.trim(), status: "approved" } },
      {
        onSuccess: () => toast.success("Reply approved"),
        onError: () => toast.error("Could not approve this reply"),
      },
    );
  }

  async function copyReply() {
    try {
      await navigator.clipboard.writeText(draft);
      toast.success("Reply copied");
    } catch {
      toast.error("Copying isn't available in this browser");
    }
  }

  const hasReply = Boolean(review.reply_text);
  const overLimit = draft.length > 500;

  return (
    <article className="surface-card p-5 transition-shadow hover:shadow-[var(--shadow-lift)]">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-display text-base font-semibold">{review.author_name}</h3>
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              {review.source}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-0.5" aria-label={`${review.rating} out of 5`}>
            {[1, 2, 3, 4, 5].map((star) => (
              <Star
                key={star}
                className={`size-3.5 ${
                  star <= review.rating ? "fill-warning text-warning" : "text-border"
                }`}
              />
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {review.detected_sentiment ? (
            <Badge className={SENTIMENT_STYLE[review.detected_sentiment]}>
              {review.detected_sentiment}
            </Badge>
          ) : (
            hasReply && <Badge variant="outline">tone unknown</Badge>
          )}
          {review.detected_tags.map((tag) => (
            <Badge key={tag} variant="outline">
              {tag}
            </Badge>
          ))}
          {review.status === "approved" && (
            <Badge className="border-transparent bg-accent text-accent-foreground">approved</Badge>
          )}
        </div>
      </header>

      <p className="mt-3 text-sm leading-relaxed text-foreground/90">{review.review_text}</p>

      {failed && (
        <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
          <span className="flex items-center gap-2 text-destructive">
            <TriangleAlert className="size-4" /> Reply generation failed.
          </span>
          <Button size="sm" variant="outline" onClick={runGenerate}>
            Retry
          </Button>
        </div>
      )}

      {hasReply ? (
        <div className="mt-4 space-y-3">
          <div className="space-y-1.5">
            <Textarea
              rows={3}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="bg-secondary/40"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Edits stay on this page until you approve.</span>
              <span className={overLimit ? "text-destructive" : undefined}>{draft.length}/500</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={instructions}
              maxLength={500}
              placeholder="Make it more empathetic and apologize for the wait"
              onChange={(e) => setInstructions(e.target.value)}
              className="min-w-56 flex-1"
            />
            <Button variant="secondary" onClick={runGenerate} disabled={generate.isPending}>
              <Sparkles className="size-4" />
              {generate.isPending ? "Rewriting..." : "Regenerate"}
            </Button>
            <Button variant="outline" onClick={copyReply}>
              <Copy className="size-4" />
              Copy
            </Button>
            {review.status === "draft" && (
              <Button onClick={approve} disabled={update.isPending || overLimit || !draft.trim()}>
                <Check className="size-4" />
                Approve
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={runGenerate} disabled={generate.isPending}>
            <Sparkles className="size-4" />
            {generate.isPending ? "Writing reply..." : "Generate reply"}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Delete review"
            onClick={() => remove.mutate(review.id)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      )}
    </article>
  );
}
