const assert = require("node:assert/strict");
const { execFile, spawnSync } = require("node:child_process");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { promisify } = require("node:util");
const test = require("node:test");

const execFileAsync = promisify(execFile);
const repositoryRoot = path.resolve(__dirname, "..", "..");
const helperScript = path.join(__dirname, "install-subagent.js");

test("global junction scope follows the installation link and check is read-only", { skip: process.platform !== "win32" }, async (t) => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "interact-agent-global-"));
  t.after(() => fsp.rm(root, { recursive: true, force: true }));
  const home = path.join(root, "home");
  const sourceSkill = path.join(root, "source", "interact");
  const installLink = path.join(home, ".agents", "skills", "interact");
  const bin = await setupEnvironment(root, home, sourceSkill);
  await fsp.mkdir(path.join(sourceSkill, ".git"), { recursive: true });
  await fsp.mkdir(path.dirname(installLink), { recursive: true });
  await fsp.symlink(sourceSkill, installLink, "junction");

  const check = await runInstaller("check", ["--harness", "codex", "--skill-path", installLink, "--model", "gpt-6.2-sol", "--effort", "low"], bin.env);
  assert.equal(check.readOnly, true);
  assert.equal(check.scope, "global");
  assert.equal(check.agentName, "interact-progress-global");
  assert.equal(check.ready, true);
  assert.equal(check.exists, false);
  assert.equal(await exists(path.join(home, ".codex", "agents")), false);

  const installed = await runInstaller("install", ["--harness", "codex", "--skill-path", installLink, "--model", "gpt-6.2-sol", "--effort", "low"], bin.env);
  assert.equal(installed.created, true);
  assert.equal(installed.scope, "global");
  assert.equal(installed.agentName, "interact-progress-global");
  const content = await fsp.readFile(installed.agentPath, "utf8");
  assert.match(content, /model_reasoning_effort = "low"/);
  assert.match(content, /shell_tool = true/);
  assert.match(content, /apps = false/);
  assert.ok(content.includes(path.resolve(installLink, "scripts", "interact-server.js").replaceAll("\\", "/")));
});

test("project scope uses a distinct name, reuses compatible files, and preserves conflicts", { skip: process.platform !== "win32" }, async (t) => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "interact-agent-project-"));
  t.after(() => fsp.rm(root, { recursive: true, force: true }));
  const home = path.join(root, "home");
  const workspace = path.join(root, "workspace");
  const sourceSkill = path.join(root, "source", "interact");
  const installLink = path.join(workspace, ".agents", "skills", "interact");
  const bin = await setupEnvironment(root, home, sourceSkill);
  await fsp.mkdir(path.join(sourceSkill, ".git"), { recursive: true });
  await fsp.mkdir(path.join(workspace, ".git"), { recursive: true });
  await fsp.mkdir(path.dirname(installLink), { recursive: true });
  await fsp.symlink(sourceSkill, installLink, "junction");

  const args = ["--harness", "codex", "--skill-path", installLink, "--model", "gpt-6.2-sol", "--effort", "low"];
  const check = await runInstaller("check", args, bin.env, workspace);
  assert.equal(check.scope, "project");
  assert.equal(check.projectRoot, workspace);
  assert.equal(check.agentName, "interact-progress-project");
  assert.equal(check.ready, true);

  const installed = await runInstaller("install", args, bin.env, workspace);
  assert.equal(installed.created, true);
  assert.equal(path.dirname(installed.agentPath), path.join(workspace, ".codex", "agents"));
  const before = await fsp.stat(installed.agentPath);
  const contentsBefore = await fsp.readFile(installed.agentPath, "utf8");
  const rerun = await runInstaller("install", args, bin.env, workspace);
  const after = await fsp.stat(installed.agentPath);
  assert.equal(rerun.reused, true);
  assert.equal(rerun.created, false);
  assert.equal(after.mtimeMs, before.mtimeMs);
  assert.equal(await fsp.readFile(installed.agentPath, "utf8"), contentsBefore);

  const conflictDir = path.join(root, "conflict-agents");
  const conflictFile = path.join(conflictDir, "interact-progress-project.toml");
  await fsp.mkdir(conflictDir, { recursive: true });
  await fsp.writeFile(conflictFile, "keep this user agent\n", "utf8");
  const conflictArgs = [...args, "--agent-dir", conflictDir];
  const conflictCheck = await runInstaller("check", conflictArgs, bin.env, workspace);
  assert.equal(conflictCheck.ready, false);
  assert.ok(conflictCheck.issues.some((issue) => issue.includes("will not be overwritten")));
  await assert.rejects(runInstaller("install", conflictArgs, bin.env, workspace));
  assert.equal(await fsp.readFile(conflictFile, "utf8"), "keep this user agent\n");
});

test("missing model or effort fails the read-only readiness check", async (t) => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "interact-agent-model-"));
  t.after(() => fsp.rm(root, { recursive: true, force: true }));
  const home = path.join(root, "home");
  const sourceSkill = path.join(root, "source", "interact");
  const link = path.join(home, ".agents", "skills", "interact");
  const bin = await setupEnvironment(root, home, sourceSkill);
  await fsp.mkdir(path.dirname(link), { recursive: true });
  await fsp.symlink(sourceSkill, link, "junction");

  const check = await runInstaller("check", ["--harness", "codex", "--skill-path", link, "--model", "gpt-6.2-sol"], bin.env);
  assert.equal(check.ready, false);
  assert.ok(check.issues.some((issue) => issue.includes("--effort")));
  assert.equal(await exists(path.join(home, ".codex", "agents")), false);
});

test("all harness templates render and parse with their native formats", { skip: process.platform !== "win32" }, async (t) => {
  const root = await fsp.mkdtemp(path.join(os.tmpdir(), "interact-agent-formats-"));
  t.after(() => fsp.rm(root, { recursive: true, force: true }));
  const home = path.join(root, "home");
  const workspace = path.join(root, "workspace");
  const sourceSkill = path.join(root, "source", "interact");
  const bin = await setupEnvironment(root, home, sourceSkill);
  await fsp.mkdir(path.join(workspace, ".git"), { recursive: true });
  const skillLink = path.join(workspace, ".agents", "skills", "interact");
  await fsp.mkdir(path.dirname(skillLink), { recursive: true });
  await fsp.symlink(sourceSkill, skillLink, "junction");

  const codex = await runInstaller("install", ["--harness", "codex", "--scope", "project", "--project-root", workspace, "--skill-path", skillLink, "--model", "gpt-6.2-sol", "--effort", "low", "--agent-dir", path.join(root, "codex-agents")], bin.env, workspace);
  const codexText = await fsp.readFile(codex.agentPath, "utf8");
  assert.match(codexText, /model_reasoning_effort = "low"/);
  assert.match(codexText, /shell_tool = true/);
  assert.match(codexText, /apps = false/);

  const claude = await runInstaller("install", ["--harness", "claude", "--scope", "project", "--project-root", workspace, "--skill-path", skillLink, "--model", "haiku", "--effort", "low", "--agent-dir", path.join(root, "claude-agents")], bin.env, workspace);
  const claudeText = await fsp.readFile(claude.agentPath, "utf8");
  assert.match(claudeText, /model: haiku/);
  assert.match(claudeText, /effort: low/);
  assert.match(claudeText, /tools: Bash/);
  assert.match(claudeText, /PreToolUse/);
  assert.match(claudeText, /shell: powershell/);
  assert.match(claudeText, /validate-progress-publish\.js/);

  const opencode = await runInstaller("install", ["--harness", "opencode", "--scope", "project", "--project-root", workspace, "--skill-path", skillLink, "--model", "openai/gpt-6.2-sol#low", "--effort", "low", "--agent-dir", path.join(root, "opencode-agents")], bin.env, workspace);
  const opencodeText = await fsp.readFile(opencode.agentPath, "utf8");
  assert.match(opencodeText, /mode: subagent/);
  assert.match(opencodeText, /model: openai\/gpt-6\.2-sol#low/);
  assert.match(opencodeText, /action: "\*"[\s\S]*?effect: deny/);
  assert.match(opencodeText, /action: shell[\s\S]*?effect: allow/);
  assert.match(opencodeText, /progress-update/);

  const parsedCodex = parseNativeFormat("toml", codexText);
  const parsedClaude = parseNativeFormat("yaml", claudeText);
  const parsedOpenCode = parseNativeFormat("yaml", opencodeText);
  if (parsedCodex) {
    assert.equal(parsedCodex.name, "interact-progress-project");
    assert.equal(parsedCodex.model_reasoning_effort, "low");
  }
  if (parsedClaude) {
    assert.equal(parsedClaude.name, "interact-progress-project");
    assert.equal(parsedClaude.effort, "low");
  }
  if (parsedOpenCode) {
    assert.equal(parsedOpenCode.mode, "subagent");
    assert.equal(parsedOpenCode.model, "openai/gpt-6.2-sol#low");
  }
  if (!parsedCodex || !parsedClaude || !parsedOpenCode) t.diagnostic("Python native parsers were unavailable; checked rendered template structures instead.");
});

async function setupEnvironment(root, home, sourceSkill) {
  const binDir = path.join(root, "bin");
  await fsp.mkdir(binDir, { recursive: true });
  await fsp.mkdir(path.join(sourceSkill, "assets", "subagents"), { recursive: true });
  await fsp.mkdir(path.join(sourceSkill, "scripts"), { recursive: true });
  await fsp.cp(path.join(repositoryRoot, "interact", "assets", "subagents"), path.join(sourceSkill, "assets", "subagents"), { recursive: true });
  await fsp.copyFile(path.join(repositoryRoot, "interact", "scripts", "interact-server.js"), path.join(sourceSkill, "scripts", "interact-server.js"));
  await fsp.copyFile(helperScript, path.join(sourceSkill, "scripts", "install-subagent.js"));
  await fsp.copyFile(path.join(__dirname, "validate-progress-publish.js"), path.join(sourceSkill, "scripts", "validate-progress-publish.js"));
  for (const executable of ["codex.cmd", "claude.cmd", "opencode.cmd"]) {
    await fsp.writeFile(path.join(binDir, executable), "@echo off\r\n", "utf8");
  }
  const env = {
    ...process.env,
    USERPROFILE: home,
    HOME: home,
    CODEX_HOME: path.join(home, ".codex"),
    PATH: `${binDir}${path.delimiter}${process.env.PATH || ""}`,
    CLAUDE_CODE_EFFORT_LEVEL: "",
  };
  return { env };
}

async function runInstaller(command, args, env, cwd = repositoryRoot) {
  const { stdout } = await execFileAsync(process.execPath, [helperScript, command, ...args], { cwd, env });
  return JSON.parse(stdout);
}

async function exists(file) {
  try {
    await fsp.access(file);
    return true;
  } catch {
    return false;
  }
}

function parseNativeFormat(format, content) {
  const code = format === "toml"
    ? "import json,sys,tomllib; print(json.dumps(tomllib.loads(sys.stdin.read())))"
    : "import json,sys,yaml; print(json.dumps(yaml.safe_load(sys.stdin.read().split('---',2)[1])))";
  const result = spawnSync("python", ["-c", code], { input: content, encoding: "utf8" });
  if (result.error?.code === "ENOENT" || /No module named ['\"]yaml/.test(result.stderr || "")) return null;
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return JSON.parse(result.stdout);
}
