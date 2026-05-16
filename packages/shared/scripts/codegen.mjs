#!/usr/bin/env node
/**
 * Codegen: baca semua `schema/*.json` → hasilkan types TS di `generated/ts/`.
 *
 * Phase 0: cuma TS. Pydantic codegen (Python) ditambah di Phase 1 pakai
 * `datamodel-code-generator` (dijalanin dari `apps/api/` via uv).
 */
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const SCHEMA_DIR = join(ROOT, "schema");
const OUT_TS_DIR = join(ROOT, "generated", "ts");

async function main() {
  const files = (await readdir(SCHEMA_DIR)).filter((f) => f.endsWith(".json"));
  if (files.length === 0) {
    console.error("No schema files found in", SCHEMA_DIR);
    process.exit(1);
  }
  await mkdir(OUT_TS_DIR, { recursive: true });

  // Dynamic import supaya tidak fail kalau dependency belum diinstall.
  let compileFromFile;
  try {
    ({ compileFromFile } = await import("json-schema-to-typescript"));
  } catch {
    console.error(
      "\n[codegen] Dependency `json-schema-to-typescript` belum terinstall.\n" +
        "Jalankan: pnpm --filter @poi/shared install\n",
    );
    process.exit(1);
  }

  for (const file of files) {
    const full = join(SCHEMA_DIR, file);
    console.log(`[codegen] compiling ${file} ...`);
    const ts = await compileFromFile(full, {
      cwd: SCHEMA_DIR,
      bannerComment: `/* eslint-disable */\n// AUTO-GENERATED from schema/${file}. Do not edit manually.`,
      additionalProperties: false,
    });
    const outName = file.replace(/\.json$/, ".d.ts");
    await writeFile(join(OUT_TS_DIR, outName), ts, "utf8");
  }
  console.log(`[codegen] done → ${OUT_TS_DIR}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
