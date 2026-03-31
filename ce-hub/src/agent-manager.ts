import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';
import { execFile } from 'node:child_process';
import type { AgentDefinition } from './types.js';

const AGENTS_DIR = '/Users/jeff/culinary-engine/.claude/agents';
const CWD = '/Users/jeff/culinary-engine';
const MOCK = process.env.CE_HUB_MOCK === '1';

const MODEL_MAP: Record<string, string> = {
  'opus': 'claude-opus-4-6',
  'sonnet': 'claude-sonnet-4-6',
  'haiku': 'claude-haiku-4-5-20251001',
};

function parseFrontmatter(content: string): { meta: Record<string, string>; body: string } {
  const m = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!m) return { meta: {}, body: content };
  const meta: Record<string, string> = {};
  for (const line of m[1].split('\n')) {
    const i = line.indexOf(':');
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return { meta, body: m[2].trim() };
}

export class AgentManager {
  private defs = new Map<string, AgentDefinition>();

  async initialize(): Promise<void> {
    if (!existsSync(AGENTS_DIR)) { console.warn('[AgentManager] agents dir not found'); return; }
    for (const f of readdirSync(AGENTS_DIR).filter(f => f.endsWith('.md') && !f.startsWith('_'))) {
      try {
        const { meta, body } = parseFrontmatter(readFileSync(join(AGENTS_DIR, f), 'utf8'));
        const name = meta['name'] || basename(f, '.md');
        this.defs.set(name, {
          name, description: meta['description'] || '',
          tools: meta['tools'] ? meta['tools'].split(',').map(t => t.trim()) : [],
          model: meta['model'] || 'sonnet',
          systemPrompt: body,
        });
      } catch (e) { console.error(`[AgentManager] failed to load ${f}:`, e); }
    }
    console.log(`[AgentManager] loaded ${this.defs.size} agents`);
  }

  getDefinitions(): AgentDefinition[] { return [...this.defs.values()]; }
  listAgents() { return [...this.defs.values()].map(d => ({ name: d.name, model: d.model, description: d.description })); }

  async sendMessage(agentName: string, message: string): Promise<string> {
    const def = this.defs.get(agentName);
    if (!def) throw new Error(`Agent not found: ${agentName}`);
    if (MOCK) { await new Promise(r => setTimeout(r, 500)); return `[MOCK] ${agentName}: done`; }

    // Force sonnet for chat speed, opus only for tasks
    const model = 'sonnet';
    console.log(`[AgentManager] claude -p ${agentName} (${model})...`);

    return new Promise<string>((resolve, reject) => {
      const child = execFile('claude', [
        '-p', message,
        '--output-format', 'text',
        '--model', model,
        '--dangerously-skip-permissions',
      ], {
        cwd: CWD, timeout: 120_000, maxBuffer: 10 * 1024 * 1024,
      }, (err, stdout, stderr) => {
        if (err) {
          console.error(`[AgentManager] ${agentName} error:`, err.message);
          console.error(`[AgentManager] stderr:`, stderr);
          console.error(`[AgentManager] stdout:`, stdout);
          // If there's stdout despite error, return it (claude sometimes exits non-zero but still outputs)
          if (stdout && stdout.trim()) return resolve(stdout.trim());
          return reject(new Error(stderr || err.message));
        }
        console.log(`[AgentManager] ${agentName} responded (${stdout.length} chars)`);
        resolve(stdout.trim() || '(empty)');
      });
      child.stdin?.end();
    });
  }
}
