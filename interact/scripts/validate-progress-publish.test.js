const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

const validator = path.join(__dirname, "validate-progress-publish.js");
const serverScript = path.join(__dirname, "interact-server.js").replaceAll("\\", "/");

test("Claude command guard allows one info-only progress publication", () => {
  const schema = {
    id: "screen-1",
    title: "Working",
    fields: [{ id: "phase", type: "info", label: "Phase", description: "Implementing" }],
  };
  const command = `node "${serverScript}" progress-update --id screen-1 --schema-json '${JSON.stringify(schema)}'`;
  const result = runGuard(command);
  assert.equal(result.status, 0, result.stderr);
});

test("Claude command guard rejects other commands, shell chaining, and answer fields", () => {
  const commands = [
    `node "${serverScript}" ask --schema-json '{}'`,
    `node "${serverScript}" progress-update --id screen-1 --schema-json '{}' ; node "${serverScript}" stop`,
    `node "${serverScript}" progress-update --id screen-1 --schema-json '${JSON.stringify({ id: "screen-1", fields: [{ id: "answer", type: "textarea", label: "Answer" }] })}'`,
  ];
  for (const command of commands) {
    const result = runGuard(command);
    assert.equal(result.status, 2, result.stderr);
  }
});

function runGuard(command) {
  return spawnSync(process.execPath, [validator, serverScript], {
    input: JSON.stringify({ tool_input: { command } }),
    encoding: "utf8",
  });
}
