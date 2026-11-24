#!/usr/bin/env node

const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

main().catch((error) => {
  process.stderr.write(`${error.message || error}\n`);
  process.exitCode = 1;
});

async function main() {
  const [command = "help", ...rest] = process.argv.slice(2);
  const args = parseArgs(rest);
  if (command === "help" || args.help) {
    printHelp();
    return;
  }

  if (command !== "check" && command !== "install") {
    throw new Error(`Unknown command: ${command}`);
  }

  const context = makeContext(args);
  const check = await inspectTarget(context);
  if (command === "check") {
    printJson(check);
    return;
  }

  if (check.issues.length > 0) {
    printJson({ ...check, command: "install", readOnly: false, installed: false });
    process.exitCode = 1;
    return;
  }

  if (check.exists) {
    printJson({ ...check, command: "install", readOnly: false, installed: true, created: false, reused: true });
    return;
  }

  const template = await fsp.readFile(context.templatePath, "utf8");
  const rendered = renderTemplate(template, context);
  await fsp.mkdir(path.dirname(context.agentPath), { recursive: true });
  try {
    await fsp.writeFile(context.agentPath, rendered, { encoding: "utf8", flag: "wx" });
  } catch (error) {
    if (error.code !== "EEXIST") throw error;
    const existing = await fsp.readFile(context.agentPath, "utf8");
    const reusable = isReusable(context, existing);
    printJson({
      ...check,
      command: "install",
      readOnly: false,
      exists: true,
      reusable,
      installed: reusable,
      created: false,
      reused: reusable,
      issues: reusable ? [] : [`An incompatible agent file appeared during install: ${context.agentPath}`],
    });
    if (!reusable) process.exitCode = 1;
    return;
  }

  printJson({ ...check, command: "install", readOnly: false, installed: true, created: true, reused: false });
}

function makeContext(args) {
  const scriptPath = process.argv[1] || __filename;
  const skillPath = path.resolve(args["skill-path"] || path.resolve(path.dirname(scriptPath), ".."));
  const harness = normalizeHarness(args.harness || detectHarness());
  const projectRoot = args["project-root"] ? path.resolve(args["project-root"]) : findProjectRoot(skillPath);
  const scope = normalizeScope(args.scope || inferScope(skillPath, projectRoot));
  const model = String(args.model || "").trim();
  const effort = String(args.effort || "").trim().toLowerCase();
  const agentName = scope === "global" ? "interact-progress-global" : "interact-progress-project";
  const fileExtension = harness === "codex" ? ".toml" : ".md";
  const filePrefix = harness === "codex" ? "codex" : harness;
  const templatePath = path.join(skillPath, "assets", "subagents", `${filePrefix}.${harness === "codex" ? "toml" : "md"}.template`);
  const defaultAgentDir = resolveAgentDirectory(harness, scope, projectRoot);
  const agentDirectory = args["agent-dir"] ? path.resolve(args["agent-dir"]) : defaultAgentDir;
  const agentPath = agentDirectory ? path.join(agentDirectory, `${agentName}${fileExtension}`) : null;
  const serverPath = path.resolve(skillPath, "scripts", "interact-server.js");
  const validatorPath = path.resolve(skillPath, "scripts", "validate-progress-publish.js");
  return {
    harness,
    scope,
    skillPath,
    projectRoot,
    model,
    effort,
    agentName,
    templatePath,
    agentPath,
    serverPath,
    validatorPath,
    harnessBinary: findHarnessBinary(harness),
    runtimeEffort: runtimeEffort(harness),
  };
}

async function inspectTarget(context) {
  const issues = [];
  if (!context.harness) issues.push("Could not determine the active harness; pass --harness.");
  if (!context.scope) issues.push("Could not determine whether the active skill is global or project-scoped; pass --scope.");
  if (context.scope === "project" && !context.projectRoot) issues.push("Project root is unknown; pass --project-root.");
  if (!context.model) issues.push("Pass the model verified as available in the active harness with --model.");
  if (!context.effort) issues.push("Pass the reasoning level verified as effective in the active harness with --effort.");
  if (context.effort && !["low", "medium", "high", "xhigh", "max"].includes(context.effort)) {
    issues.push(`Unsupported reasoning level: ${context.effort}`);
  }
  if (context.harness === "claude" && context.model && !/haiku/i.test(context.model)) {
    issues.push("Claude progress agents should use a Haiku model.");
  }
  if (context.harness === "opencode" && context.model && !/#low$/i.test(context.model)) {
    issues.push("OpenCode model must include a verified low reasoning variant, for example provider/model#low.");
  }
  if (context.runtimeEffort && context.runtimeEffort !== context.effort) {
    issues.push(`The harness environment overrides the requested effort (${context.runtimeEffort} vs ${context.effort}).`);
  }
  if (!context.harnessBinary) issues.push(`The ${context.harness || "active"} harness executable was not found on PATH.`);
  if (!context.templatePath || !fs.existsSync(context.templatePath)) {
    issues.push(`Subagent template not found: ${context.templatePath}`);
  }
  if (!fs.existsSync(context.serverPath)) issues.push(`Interact server script not found: ${context.serverPath}`);
  if (context.harness === "claude" && !fs.existsSync(context.validatorPath)) {
    issues.push(`Claude command validator not found: ${context.validatorPath}`);
  }

  const exists = Boolean(context.agentPath && fs.existsSync(context.agentPath));
  let reusable = false;
  if (exists && context.harness) {
    const existing = await fsp.readFile(context.agentPath, "utf8");
    reusable = isReusable(context, existing);
    if (!reusable) issues.push(`An incompatible file already exists and will not be overwritten: ${context.agentPath}`);
  }

  return {
    command: "check",
    readOnly: true,
    harness: context.harness,
    harnessBinary: context.harnessBinary,
    skillPath: context.skillPath,
    scope: context.scope,
    projectRoot: context.scope === "project" ? context.projectRoot : null,
    agentName: context.agentName,
    agentPath: context.agentPath,
    exists,
    reusable,
    model: context.model || null,
    reasoningEffort: context.effort || null,
    effectiveRuntimeEffort: context.runtimeEffort || context.effort || null,
    templatePath: context.templatePath,
    ready: issues.length === 0,
    issues,
  };
}

function isReusable(context, content) {
  if (!context.harness || !context.model || !context.effort || !content.includes(context.agentName) || !content.includes(context.model)) return false;
  const expectedServer = normalizePath(context.serverPath).toLowerCase();
  const normalizedContent = normalizePath(content).toLowerCase();
  if (!normalizedContent.includes(expectedServer)) return false;
  if (!content.includes("Interact progress publisher") || !content.includes("progress-update")) return false;

  if (context.harness === "codex") {
    return content.includes(`model_reasoning_effort = "${context.effort}"`)
      && content.includes("[features]")
      && content.includes("shell_tool = true");
  }
  if (context.harness === "claude") {
    return content.includes(`effort: ${context.effort}`)
      && content.includes("tools: Bash")
      && content.includes("PreToolUse")
      && normalizePath(content).toLowerCase().includes(normalizePath(context.validatorPath).toLowerCase());
  }
  return context.harness === "opencode"
    && content.includes("mode: subagent")
    && /action:\s*["']?\*["']?\s*\n\s*resource:\s*["']?\*["']?\s*\n\s*effect:\s*deny/.test(content)
    && content.includes("action: shell");
}

function renderTemplate(template, context) {
  const serverPath = normalizePath(context.serverPath);
  const validatorPath = normalizePath(context.validatorPath);
  const commandPattern = `node "${serverPath}" progress-update --id * --schema-json *`;
  const replacements = {
    AGENT_NAME: context.agentName,
    MODEL: context.model,
    EFFORT: context.effort,
    INTERACT_SERVER_TOML: JSON.stringify(serverPath),
    INTERACT_SERVER_PATH_YAML: JSON.stringify(serverPath),
    VALIDATOR_PATH_YAML: JSON.stringify(validatorPath),
    PUBLISH_COMMAND_PATTERN_YAML: JSON.stringify(commandPattern),
  };
  return template.replace(/\{\{([A-Z_]+)\}\}/g, (match, key) => {
    if (!Object.prototype.hasOwnProperty.call(replacements, key)) {
      throw new Error(`Unknown template placeholder: ${key}`);
    }
    return replacements[key];
  });
}

function resolveAgentDirectory(harness, scope, projectRoot) {
  if (!harness || !scope) return null;
  if (scope === "project") {
    if (!projectRoot) return null;
    const folders = { codex: ".codex", claude: ".claude", opencode: ".opencode" };
    return path.join(projectRoot, folders[harness], "agents");
  }
  const home = os.homedir();
  if (harness === "codex") return path.join(process.env.CODEX_HOME || path.join(home, ".codex"), "agents");
  if (harness === "claude") return path.join(process.env.CLAUDE_CONFIG_DIR || path.join(home, ".claude"), "agents");
  const configHome = process.env.XDG_CONFIG_HOME || path.join(home, ".config");
  return path.join(configHome, "opencode", "agents");
}

function inferScope(skillPath, projectRoot) {
  const home = os.homedir();
  const globalRoots = [
    path.join(home, ".agents", "skills"),
    path.join(process.env.CODEX_HOME || path.join(home, ".codex"), "skills"),
    path.join(process.env.CLAUDE_CONFIG_DIR || path.join(home, ".claude"), "skills"),
    path.join(process.env.XDG_CONFIG_HOME || path.join(home, ".config"), "opencode", "skills"),
  ];
  if (globalRoots.some((root) => isWithin(skillPath, root))) return "global";

  const projectSkillRoots = [".agents/skills", ".codex/skills", ".claude/skills", ".opencode/skills"];
  if (projectRoot && projectSkillRoots.some((suffix) => isWithin(skillPath, path.join(projectRoot, ...suffix.split("/"))))) {
    return "project";
  }
  return null;
}

function findProjectRoot(startPath) {
  const skillPath = path.resolve(startPath);
  const skillParent = path.dirname(skillPath);
  const skillContainer = path.basename(skillParent).toLowerCase() === "skills"
    && [".agents", ".codex", ".claude", ".opencode"].includes(path.basename(path.dirname(skillParent)).toLowerCase())
    ? skillParent
    : skillPath;
  let current = skillContainer;
  while (true) {
    if (fs.existsSync(path.join(current, ".git")) || fs.existsSync(path.join(current, ".hg"))) return current;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

function isWithin(candidate, parent) {
  const relative = path.relative(path.resolve(parent), path.resolve(candidate));
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function detectHarness() {
  if (process.env.CODEX_HOME || process.env.CODEX_CLI_PATH || process.env.CODEX_THREAD_ID) return "codex";
  if (process.env.CLAUDECODE || process.env.CLAUDE_CODE || process.env.CLAUDE_CODE_SSE_PORT) return "claude";
  if (process.env.OPENCODE || process.env.OPENCODE_CONFIG) return "opencode";
  return null;
}

function findHarnessBinary(harness) {
  const names = { codex: ["codex"], claude: ["claude"], opencode: ["opencode"] }[harness] || [];
  const suffixes = process.platform === "win32" ? [".exe", ".cmd", ".bat", ".ps1", ""] : [""];
  const pathEntries = (process.env.PATH || "").split(path.delimiter).filter(Boolean);
  for (const directory of pathEntries) {
    for (const name of names) {
      for (const suffix of suffixes) {
        const candidate = path.join(directory, `${name}${suffix}`);
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  }
  return null;
}

function runtimeEffort(harness) {
  if (harness === "claude") return process.env.CLAUDE_CODE_EFFORT_LEVEL || null;
  if (harness === "opencode") return null;
  return null;
}

function normalizeHarness(value) {
  return ["codex", "claude", "opencode"].includes(String(value || "").toLowerCase())
    ? String(value).toLowerCase()
    : null;
}

function normalizeScope(value) {
  return ["global", "project"].includes(String(value || "").toLowerCase())
    ? String(value).toLowerCase()
    : null;
}

function normalizePath(value) {
  return String(value || "").replaceAll("\\", "/");
}

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith("--")) continue;
    const key = item.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) parsed[key] = true;
    else {
      parsed[key] = next;
      index += 1;
    }
  }
  return parsed;
}

function printJson(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function printHelp() {
  process.stdout.write(`Usage:\n  node install-subagent.js check --harness <codex|claude|opencode> --scope <global|project> --model <model> --effort <low|medium|high> [--skill-path <path>] [--project-root <path>] [--agent-dir <path>]\n  node install-subagent.js install --harness <codex|claude|opencode> --scope <global|project> --model <model> --effort <low|medium|high> [--skill-path <path>] [--project-root <path>] [--agent-dir <path>]\n\ncheck only reads files. install creates a missing agent definition and never replaces an existing file.\n`);
}
