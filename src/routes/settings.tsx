import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { AppShell } from "@/components/reputation/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { settingsQueryOptions, useSaveSettings } from "@/services/reputation/hooks";
import { businessSettingsSchema, type BusinessSettings } from "@/services/reputation/types";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Business profile — Reputation Manager" },
      {
        name: "description",
        content:
          "Set your business name, type, description and brand voice so every AI review reply sounds like you.",
      },
      { property: "og:title", content: "Business profile — Reputation Manager" },
      {
        property: "og:description",
        content: "Tune the brand voice used for every generated review reply.",
      },
    ],
  }),
  component: SettingsPage,
});

const EMPTY: BusinessSettings = {
  business_name: "",
  business_type: "",
  description: "",
  brand_voice: "",
};

function SettingsPage() {
  const { data, isLoading } = useQuery(settingsQueryOptions);
  const save = useSaveSettings();
  const [form, setForm] = useState<BusinessSettings>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const set = (key: keyof BusinessSettings) => (value: string) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const parsed = businessSettingsSchema.safeParse(form);
    if (!parsed.success) {
      const next: Record<string, string> = {};
      for (const issue of parsed.error.issues) next[String(issue.path[0])] = issue.message;
      setErrors(next);
      return;
    }
    setErrors({});
    save.mutate(parsed.data, {
      onSuccess: () => toast.success("Business profile saved"),
      onError: () => toast.error("Could not save your profile"),
    });
  }

  return (
    <AppShell>
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold">Business profile</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This context is blended into every reply, so answers sound like your business and not a
          robot.
        </p>

        <form onSubmit={submit} className="surface-card mt-6 space-y-5 p-6">
          <Field label="Business name" error={errors["business_name"]}>
            <Input
              value={form.business_name}
              maxLength={100}
              placeholder="Daily Grind Cafe"
              onChange={(e) => set("business_name")(e.target.value)}
            />
          </Field>
          <Field label="Business type" error={errors["business_type"]}>
            <Input
              value={form.business_type}
              maxLength={50}
              placeholder="Coffee Shop"
              onChange={(e) => set("business_type")(e.target.value)}
            />
          </Field>
          <Field
            label="What should replies know about you?"
            error={errors["description"]}
            hint={`${form.description.length}/1000`}
          >
            <Textarea
              value={form.description}
              maxLength={1000}
              rows={4}
              placeholder="Cozy local cafe serving organic brews and homemade pastries."
              onChange={(e) => set("description")(e.target.value)}
            />
          </Field>
          <Field label="Tone of voice" error={errors["brand_voice"]}>
            <Input
              value={form.brand_voice}
              maxLength={100}
              placeholder="warm, welcoming, and slightly playful"
              onChange={(e) => set("brand_voice")(e.target.value)}
            />
          </Field>

          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" disabled={save.isPending || isLoading}>
              {save.isPending ? "Saving..." : "Save profile"}
            </Button>
            {isLoading && <span className="text-sm text-muted-foreground">Loading...</span>}
          </div>
        </form>
      </div>
    </AppShell>
  );
}

function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string;
  error?: string | undefined;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label>{label}</Label>
        {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      </div>
      {children}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
