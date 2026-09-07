import { reviewCreateSchema, type ImportRowError, type ReviewCreate } from "./types";

export const CSV_MAX_BYTES = 1024 * 1024; // 1 MB (AC-04)
export const CSV_MAX_ROWS = 100; // AC-04
export const REQUIRED_HEADERS = ["author_name", "review_text", "rating"] as const;

export interface ParsedCsv {
  valid: ReviewCreate[];
  errors: ImportRowError[];
}

/** Minimal RFC4180-ish splitter handling quoted fields and escaped quotes. */
export function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else quoted = false;
      } else cur += ch;
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out.map((v) => v.trim());
}

/**
 * Parses a review CSV, enforcing AC-04/AC-05 and gracefully skipping bad rows
 * (AC-06). Throws for whole-file rejections (400-class failures).
 */
export function parseReviewCsv(text: string): ParsedCsv {
  const bytes = new TextEncoder().encode(text).length;
  if (bytes > CSV_MAX_BYTES) {
    throw new Error("CSV file exceeds the 1 MB size limit");
  }

  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length === 0) throw new Error("CSV file is empty");

  const headers = splitCsvLine(lines[0]).map((h) => h.toLowerCase());
  const missing = REQUIRED_HEADERS.filter((h) => !headers.includes(h));
  if (missing.length > 0) {
    throw new Error(`CSV is missing required column(s): ${missing.join(", ")}`);
  }

  const rows = lines.slice(1);
  if (rows.length > CSV_MAX_ROWS) {
    throw new Error(`CSV contains ${rows.length} reviews; the limit is ${CSV_MAX_ROWS}`);
  }

  const valid: ReviewCreate[] = [];
  const errors: ImportRowError[] = [];

  rows.forEach((line, index) => {
    const rowNumber = index + 2; // 1-based, header is row 1
    const cells = splitCsvLine(line);
    const get = (key: string) => cells[headers.indexOf(key)] ?? "";
    const ratingRaw = get("rating");
    const rating = Number(ratingRaw);

    if (ratingRaw === "" || !Number.isFinite(rating)) {
      errors.push({ row: rowNumber, error: "Rating must be between 1 and 5" });
      return;
    }

    const parsed = reviewCreateSchema.safeParse({
      author_name: get("author_name"),
      review_text: get("review_text"),
      rating,
      source: "csv",
    });

    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      const field = String(issue.path[0] ?? "row");
      const message =
        field === "rating"
          ? "Rating must be between 1 and 5"
          : field === "author_name"
            ? "Author name cannot be empty"
            : "Review text must be 3-5000 characters";
      errors.push({ row: rowNumber, error: message });
      return;
    }

    valid.push(parsed.data);
  });

  return { valid, errors };
}
