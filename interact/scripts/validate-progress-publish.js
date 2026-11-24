#!/usr/bin/env node

const path = require("node:path");

const expectedServerPath = normalizePath(path.resolve(process.argv[2] || ""));
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  try {
    const hook = JSON.parse(input || "{}");
    const command = String(hook.tool_input?.command || "");
    const pattern = new RegExp(
      `^node\\s+"${escapeRegExp(expectedServerPath)}"\\s+progress-update\\s+--id\\s+([A-Za-z0-9._-]+)\\s+--schema-json\\s+'((?:[^']|'')*)'\\s*$`,
      "i",
    );
    const match = command.match(pattern);
    if (!expectedServerPath || !match) throw new Error("Only one interact-server progress-update command is allowed.");

    const interactionId = match[1];
    const schemaText = match[2].replace(/''/g, "'");
    const schema = JSON.parse(schemaText);
    if (schema.id && schema.id !== interactionId) throw new Error("Schema ID must match the command's interaction ID.");
    if (!Array.isArray(schema.fields) || schema.fields.length === 0 || !schema.fields.every((field) => field.type === "info")) {
      throw new Error("The publication schema must contain info-only fields.");
    }
  } catch (error) {
    process.stderr.write(`${error.message || error}\n`);
    process.exitCode = 2;
  }
});

function normalizePath(value) {
  return String(value || "").replaceAll("\\", "/").replace(/\/$/, "");
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
