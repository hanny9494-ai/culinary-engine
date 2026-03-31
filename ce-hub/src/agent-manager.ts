import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { join, basename } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import type { AgentDefinition } from './types.js';

const execFileAsync = promisify(execFile);
const AGENTS_DIR = '/Users/jeff/culinary-engine/.claude/agents';
const CWD = '/Users/jeff/culinary-engine';
const MOCK = process.env.CE_HUB_MOCK === '1';

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
          model: meta['model'] || 'claude-sonnet-4-6',
          systemPrompt: body,
        });
      } catch (e) { console.error(`[AgentManager] failed to load ${f}:`, e); }
    }
    console.log(`[AgentManager] loaded ${this.defs.size} agents`);
  }

  getDefinitions(): AgentDefinition[] { return [...this.defs.values()]; }

  listAgents() {
    return [...this.defs.values()].map(d => ({ name: d.name, model: d.model, description: d.description }));
  }

  async sendMessage(agentName: string, message: string): Promise<string> {
    const def = this.defs.get(agentName);
    if (!def) throw new Error(`Agent not found: ${agentName}`);
    if (MOCK) { await new Promise(r => setTimeout(r, 500)); return `[MOCK] ${agentName}: done`; }

    const env = { ...process.env, ANTHROPIC_BASE_URL: process.env.ANTHROPIC_BASE_URL || 'http://localhost:3001', http_proxy: '', https_proxy: '', HTTP_PROXY: '', HTTPS_PROXY: '' };
    const { stdout } = await execFileAsync('claude', ['-p', message, '--output-format', 'json', '--model', def.model, '--permission-mode', 'bypassPermissions', '--cwd', CWD], {
      env, cwd: CWD, timeout: 300_000, maxBuffer: 10 * 1024 * 1024,
    });
    try { const p = JSON.parse(stdout); return p.result || p.content || stdout; } catch { return stdout.trim(); }
  }
}
