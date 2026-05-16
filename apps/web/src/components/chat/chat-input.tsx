"use client";

import { Loader2, Send } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const MAX_HEIGHT_PX = 220;
const MIN_PROMPT_LENGTH = 4;

interface ChatInputProps {
  onSubmit: (prompt: string) => void;
  disabled?: boolean;
  pending?: boolean;
  placeholder?: string;
  className?: string;
}

export function ChatInput({
  onSubmit,
  disabled,
  pending,
  placeholder = "Ketik kebutuhan data, misal: 'data dokter spesialis jantung di RS Siloam Karawaci'",
  className,
}: ChatInputProps) {
  const [value, setValue] = React.useState("");
  const ref = React.useRef<HTMLTextAreaElement>(null);

  // Auto-resize berdasarkan konten.
  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  const trimmed = value.trim();
  const valid = trimmed.length >= MIN_PROMPT_LENGTH;
  const isDisabled = disabled || pending;

  const submit = () => {
    if (!valid || isDisabled) return;
    onSubmit(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className={cn(
        "border-border bg-background focus-within:ring-ring/30 flex items-end gap-2 rounded-xl border p-2 shadow-sm transition focus-within:ring-2",
        className,
      )}
    >
      <Textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        rows={1}
        className="min-h-[44px] resize-none border-0 bg-transparent px-2 py-2 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
        aria-label="Chat prompt"
      />
      <Button type="submit" size="icon" disabled={!valid || isDisabled} aria-label="Kirim prompt">
        {pending ? <Loader2 className="animate-spin" /> : <Send />}
      </Button>
    </form>
  );
}
