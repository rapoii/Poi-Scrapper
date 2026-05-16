"use client";

import { Bot, User } from "lucide-react";
import type * as React from "react";

import { cn } from "@/lib/utils";

export type ChatRole = "user" | "system";

interface ChatMessageProps {
  role: ChatRole;
  children: React.ReactNode;
  timestamp?: string;
  className?: string;
}

export function ChatMessage({ role, children, timestamp, className }: ChatMessageProps) {
  const isUser = role === "user";
  return (
    <div className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row", className)}>
      <span
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
        aria-hidden
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className={cn("flex max-w-[85%] flex-col gap-1", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2 text-sm leading-relaxed",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-sm"
              : "bg-muted text-foreground rounded-bl-sm",
          )}
        >
          {children}
        </div>
        {timestamp && (
          <span className="text-muted-foreground px-1 text-[11px] tabular-nums">{timestamp}</span>
        )}
      </div>
    </div>
  );
}
