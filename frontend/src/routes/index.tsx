import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Inbox } from "lucide-react";
import { AppShell } from "@/components/reputation/AppShell";
import { ReviewCard } from "@/components/reputation/ReviewCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { reviewsQueryOptions, settingsQueryOptions } from "@/services/reputation/hooks";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Review queue — Reputation Manager" },
      {
        name: "description",
        content:
          "Reply to every customer review in seconds: import reviews, generate on-brand replies in one click, edit, and approve.",
      },
      { property: "og:title", content: "Review queue — Reputation Manager" },
      {
        property: "og:description",
        content: "One-click, on-brand replies for your Google, Yelp and TripAdvisor reviews.",
      },
    ],
  }),
  loader: ({ context }) => context.queryClient.ensureQueryData(reviewsQueryOptions),
  component: QueuePage,
});

function QueuePage() {
  const { data: reviews, isLoading } = useQuery(reviewsQueryOptions);
  const { data: settings } = useQuery(settingsQueryOptions);
  const [tab, setTab] = useState<"pending" | "completed">("pending");

  const pending = (reviews ?? []).filter((r) => r.status === "draft");
  const completed = (reviews ?? []).filter((r) => r.status === "approved");
  const shown = tab === "pending" ? pending : completed;

  return (
    <AppShell>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">Review queue</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {settings
              ? `Replying as ${settings.business_name} in a ${settings.brand_voice} voice.`
              : "Add your business profile to shape the tone of replies."}
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="secondary">
            <Link to="/import">Add reviews</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/settings">Edit voice</Link>
          </Button>
        </div>
      </div>

      <div className="mt-6 flex gap-1 rounded-xl border border-border bg-card p-1 sm:w-fit">
        {(
          [
            ["pending", `Needs a reply (${pending.length})`],
            ["completed", `Completed (${completed.length})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition-colors sm:flex-none ${
              tab === key
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-secondary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mt-5 space-y-4">
        {isLoading &&
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)}

        {!isLoading && shown.length === 0 && (
          <div className="surface-card flex flex-col items-center gap-3 p-12 text-center">
            <Inbox className="size-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {tab === "pending"
                ? "Nothing waiting — every review has a reply."
                : "No approved replies yet."}
            </p>
            {tab === "pending" && (
              <Button asChild size="sm">
                <Link to="/import">Add reviews</Link>
              </Button>
            )}
          </div>
        )}

        {shown.map((review) => (
          <ReviewCard key={review.id} review={review} />
        ))}
      </div>
    </AppShell>
  );
}
