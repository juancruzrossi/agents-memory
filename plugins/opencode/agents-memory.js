import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const debugEnabled = process.env.AGENTS_MEMORY_DEBUG === "1";

function agentsMemoryBin() {
  return `${process.env.HOME}/.agents-memory/bin/agents-memory`;
}

async function loadStartupContext(directory) {
  try {
    const { stdout } = await execFileAsync(
      agentsMemoryBin(),
      ["startup", "--cwd", directory, "--format", "text"],
      { maxBuffer: 1024 * 1024 },
    );
    return stdout.trim();
  } catch {
    return "";
  }
}

export const AgentsMemoryPlugin = async ({ directory }) => {
  const seenSessions = new Set();

  return {
    "experimental.chat.system.transform": async (input, output) => {
      const sessionID = input?.sessionID;
      if (sessionID && seenSessions.has(sessionID)) {
        return;
      }
      const context = await loadStartupContext(directory);
      if (context) {
        output.system.push(context);
      }
      if (debugEnabled) {
        console.error(
          `AGENTS_MEMORY: system.transform session=${sessionID ?? "unknown"} dir=${directory} chars=${context.length}`,
        );
      }
      if (sessionID) {
        seenSessions.add(sessionID);
      }
    },
    "experimental.session.compacting": async (_input, output) => {
      const context = await loadStartupContext(directory);
      if (context) {
        output.context.push(context);
      }
      if (debugEnabled) {
        console.error(
          `AGENTS_MEMORY: session.compacting dir=${directory} chars=${context.length}`,
        );
      }
    },
  };
};
