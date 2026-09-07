import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { AppShell } from "@/components/reputation/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateReview, useImportCsv } from "@/services/reputation/hooks";
import { CSV_MAX_ROWS } from "@/services/reputation/csv";
import {
  ApiError,
  reviewCreateSchema,
  type ImportSummary,
} from "@/services/reputation/types";

export const Route = createFileRoute("/import")({
  head: () => ({
    meta: [
      { title: "Add reviews — Reputation Manager" },
      {
        name: "description",
        content:
          "Add a single customer review by hand or upload up to 100 reviews at once from a CSV file.",
      },
      { property: "og:title", content: "Add reviews — Reputation Manager" },
      {
        property: "og:description",
        content: "Manual entry and bulk CSV upload for your review queue.",
      },
    ],
  }),
  component: ImportPage,
});

function ImportPage() {
  const create = useCreateReview();
  const importCsv = useImportCsv();
  const fileInput = useRef<HTMLInputElement>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [form, setForm] = useState({ author_name: "", review_text: "", rating: "5" });
  const [errors, setErrors] = useState<Record<string, string>>({});

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const parsed = reviewCreateSchema.safeParse({
      author_name: form.author_name,
      review_text: form.review_text,
      rating: Number(form.rating),
      source: "manual",
    });
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) next[String(issue.path[0])] = issue.message;
      setErrors(next);
      return;
    }
    setErrors({});
    create.mutate(parsed.data, {
      onSuccess: () => {
        toast.success("Review added to your queue");
        setForm({ author_name: "", review_text: "", rating: "5" });
      },
      onError: (error) =>
        toast.error(
          error instanceof ApiError && error.status === 409
            ? "That review is already in your queue"
            : "Could not add that review",
        ),
    });
  }

  function onFile(file: File | undefined) {
    if (!file) return;
    setSummary(null);
    importCsv.mutate(file, {
      onSuccess: (result) => {
        setSummary(result);
        toast.success(`Imported ${result.imported} review${result.imported === 1 ? "" : "s"}`);
      },
      onError: (error) =>
        toast.error(error instanceof Error ? error.message : "That file could not be imported"),
    });
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <AppShell>
      <h1 className="text-3xl font-semibold">Add reviews</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Type one in by hand, or drop in a spreadsheet export of up to {CSV_MAX_ROWS} reviews.
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <form onSubmit={submit} className="surface-card space-y-5 p-6">
          <h2 className="text-lg font-semibold">One review</h2>
          <div className="space-y-2">
            <Label>Customer name</Label>
            <Input
              value={form.author_name}
              maxLength={100}
              placeholder="John Doe"
              onChange={(e) => setForm({ ...form, author_name: e.target.value })}
            />
            {errors["author_name"] && (
              <p className="text-xs text-destructive">Name must be 1–100 characters</p>
            )}
          </div>
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <Label>What they wrote</Label>
              <span className="text-xs text-muted-foreground">{form.review_text.length}/5000</span>
            </div>
            <Textarea
              rows={5}
              maxLength={5000}
              value={form.review_text}
              placeholder="Great espresso but service was a bit slow today."
              onChange={(e) => setForm({ ...form, review_text: e.target.value })}
            />
            {errors["review_text"] && (
              <p className="text-xs text-destructive">Review must be 3–5000 characters</p>
            )}
          </div>
          <div className="space-y-2">
            <Label>Star rating</Label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setForm({ ...form, rating: String(value) })}
                  className={`size-10 rounded-lg border text-sm font-medium transition-colors ${
                    Number(form.rating) === value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-muted-foreground hover:bg-secondary"
                  }`}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Adding..." : "Add to queue"}
          </Button>
        </form>

        <div className="surface-card space-y-4 p-6">
          <h2 className="text-lg font-semibold">Bulk upload</h2>
          <p className="text-sm text-muted-foreground">
            The file needs the columns <code className="text-foreground">author_name</code>,{" "}
            <code className="text-foreground">review_text</code> and{" "}
            <code className="text-foreground">rating</code>. Max 1 MB and {CSV_MAX_ROWS} rows; bad
            rows are skipped and reported back to you.
          </p>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <Button
            type="button"
            variant="secondary"
            disabled={importCsv.isPending}
            onClick={() => fileInput.current?.click()}
          >
            <Upload className="size-4" />
            {importCsv.isPending ? "Reading file..." : "Choose CSV file"}
          </Button>

          {summary && (
            <div className="rounded-xl border border-border bg-secondary/50 p-4 text-sm">
              <p className="font-medium">
                {summary.imported} added · {summary.skipped} skipped
              </p>
              {summary.errors.length > 0 && (
                <ul className="mt-2 space-y-1 text-muted-foreground">
                  {summary.errors.slice(0, 8).map((issue) => (
                    <li key={`${issue.row}-${issue.error}`}>
                      Row {issue.row}: {issue.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
