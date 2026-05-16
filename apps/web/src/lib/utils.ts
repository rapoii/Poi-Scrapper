import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Standard shadcn utility: merge Tailwind classes sambil resolve konflik.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
