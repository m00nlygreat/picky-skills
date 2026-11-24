const assert = require("node:assert/strict");
const { execFile } = require("node:child_process");
const fsp = require("node:fs/promises");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { promisify } = require("node:util");
const test = require("node:test");

const execFileAsync = promisify(execFile);
const serverScript = path.join(__dirname, "interact-server.js");

test("progress updates stay on one SSE connection and cannot overwrite a question", async (t) => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "interact-progress-"));
  const id = "progress-test";
  const port = await getFreePort();
  const infoSchema = (title, description) => ({
    id,
    title,
    description,
    fields: [{ id: "status", type: "info", label: "Status", description }],
  });

  t.after(async () => {
    await runCli("stop", "--root", root).catch(() => {});
    await fsp.rm(root, { recursive: true, force: true });
  });

  const opened = await runCli("ask", "--root", root, "--port", String(port), "--schema-json", JSON.stringify(infoSchema("Progress started", "Starting")));
  const baseUrl = new URL(opened.url).origin;
  const abortController = new AbortController();
  const eventResponse = await fetch(`${baseUrl}/api/interactions/${id}/events`, { signal: abortController.signal });
  assert.equal(eventResponse.status, 200);
  const events = createEventReader(eventResponse.body.getReader());

  const initialEvent = await events.next();
  assert.equal(initialEvent.id, id);
  await acknowledge(baseUrl, initialEvent);

  const first = await runCli("progress-update", "--root", root, "--id", id, "--schema-json", JSON.stringify(infoSchema("Inspection", "Server checks are in place")));
  assert.equal(first.publication.sseClients, 1);
  const firstEvent = await events.next();
  assert.equal(firstEvent.title, "Inspection");
  await acknowledge(baseUrl, firstEvent);

  const second = await runCli("progress-update", "--root", root, "--id", id, "--schema-json", JSON.stringify(infoSchema("Installation", "Preparing the scoped installer")));
  assert.equal(second.publication.sseClients, 1);
  const secondEvent = await events.next();
  assert.equal(secondEvent.title, "Installation");
  assert.notEqual(secondEvent.updatedAt, firstEvent.updatedAt);
  await acknowledge(baseUrl, secondEvent);

  const measured = await runCli("metrics", "--root", root, "--id", id);
  assert.equal(measured.metrics.length, 3);
  assert.ok(measured.metrics.every((metric) => metric.requestToSseReceiveMs >= 0));
  assert.ok(measured.metrics.every((metric) => metric.sseWriteToAckMs >= 0));
  t.diagnostic(`request-to-SSE receipt: first screen=${measured.metrics[0].requestToSseReceiveMs}ms, first update=${measured.metrics[1].requestToSseReceiveMs}ms, follow-up update=${measured.metrics[2].requestToSseReceiveMs}ms`);

  const question = {
    id,
    title: "Need your choice",
    fields: [{ id: "choice", type: "text", label: "Choice", required: true }],
  };
  await runCli("ask", "--root", root, "--port", String(port), "--schema-json", JSON.stringify(question));
  const questionEvent = await events.next();
  assert.equal(questionEvent.title, "Need your choice");
  assert.equal(questionEvent.fields[0].type, "text");

  await assert.rejects(
    runCli("progress-update", "--root", root, "--id", id, "--schema-json", JSON.stringify(infoSchema("Late update", "Must not replace the question"))),
    (error) => error.code === 1
      && `${error.stderr || ""}${error.stdout || ""}${error.message || ""}`.includes("progress updates require the active info-only screen"),
  );
  const current = await fetch(`${baseUrl}/api/interactions/${id}`).then((response) => response.json());
  assert.equal(current.title, "Need your choice");
  assert.equal(current.fields[0].type, "text");

  await runCli("ask", "--root", root, "--port", String(port), "--schema-json", JSON.stringify(infoSchema("Race setup", "Info screen before concurrent writes")));
  const raceSetupEvent = await events.next();
  assert.equal(raceSetupEvent.title, "Race setup");
  const directProgressPromise = fetch(`${baseUrl}/api/interactions/${id}/progress`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ interaction: infoSchema("Racing progress", "May be rejected"), requestStartedAt: Date.now() }),
  });
  const directQuestionPromise = fetch(`${baseUrl}/api/interactions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ interaction: question, clearAnswers: true, requestStartedAt: Date.now() }),
  });
  const [directFirst, directQuestion] = await Promise.all([directProgressPromise, directQuestionPromise]);
  assert.equal(directQuestion.status, 200);
  assert.ok([200, 409].includes(directFirst.status));
  const afterRace = await fetch(`${baseUrl}/api/interactions/${id}`).then((response) => response.json());
  assert.equal(afterRace.title, "Need your choice");
  assert.equal(afterRace.fields[0].type, "text");

  await fetch(`${baseUrl}/api/interactions/${id}/answer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ values: { choice: "first" } }),
  }).then((response) => assert.equal(response.status, 200));
  await fetch(`${baseUrl}/api/interactions/${id}/answer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ values: { choice: "second" } }),
  }).then((response) => assert.equal(response.status, 200));
  const answer = await runCli("wait", "--root", root, "--id", id, "--after-seq", "1", "--timeout", "2");
  assert.equal(answer.seq, 2);
  assert.equal(answer.values.choice, "second");

  abortController.abort();
  await events.cancel().catch(() => {});
});

async function runCli(...args) {
  const { stdout } = await execFileAsync(process.execPath, [serverScript, ...args], { cwd: path.resolve(__dirname, "..", "..") });
  return JSON.parse(stdout);
}

async function getFreePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const port = server.address().port;
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  return port;
}

function createEventReader(reader) {
  const decoder = new TextDecoder();
  const queue = [];
  let buffer = "";
  return {
    async next() {
      while (queue.length === 0) {
        const { value, done } = await reader.read();
        assert.equal(done, false, "SSE stream closed before the next interaction arrived");
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop();
        for (const frame of frames) {
          const data = frame.split(/\r?\n/).find((line) => line.startsWith("data: "));
          if (data) queue.push(JSON.parse(data.slice(6)));
        }
      }
      return queue.shift();
    },
    cancel() {
      return reader.cancel();
    },
  };
}

async function acknowledge(baseUrl, interaction) {
  const response = await fetch(`${baseUrl}/api/interactions/${interaction.id}/events/ack`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ updatedAt: interaction.updatedAt, receivedAt: Date.now() }),
  });
  assert.equal(response.status, 200);
  return response.json();
}
