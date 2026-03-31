import React, { useState, useEffect, useCallback } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout';
import { AgentTile } from './components/AgentTile';
import { SettingsPanel } from './components/SettingsPanel';
import { useWebSocket } from './hooks/useWebSocket';
import 'react-grid-layout/css/styles.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

interface AgentInfo {
  name: string;
  model: string;
  description: string;
}

// Auto-generate layout for all agents: cc-lead big, rest 2-column grid
function generateLayout(agents: string[]) {
  const layout: any[] = [];
  const ccIdx = agents.indexOf('cc-lead');

  // cc-lead takes left half
  if (ccIdx >= 0) {
    layout.push({ i: 'cc-lead', x: 0, y: 0, w: 6, h: 14, minW: 3, minH: 4 });
  }

  // Rest go in right column, 2 wide
  const others = agents.filter(a => a !== 'cc-lead');
  let row = 0;
  for (let idx = 0; idx < others.length; idx++) {
    const col = idx % 2;
    if (col === 0 && idx > 0) row += 7;
    layout.push({
      i: others[idx],
      x: 6 + col * 3,
      y: row,
      w: 3,
      h: 7,
      minW: 2,
      minH: 3,
    });
  }
  return layout;
}

export default function App() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const { connected, messages, sendMessage, subscribe } = useWebSocket();

  useEffect(() => {
    fetch('/api/agents')
      .then(r => r.json())
      .then(data => setAgents(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, []);

  // Build agent list: always include cc-lead + all from API
  const allAgentNames = ['cc-lead', ...agents.map(a => a.name).filter(n => n !== 'cc-lead')];

  const [layouts, setLayouts] = useState<Record<string, any[]>>(() => {
    const saved = localStorage.getItem('ce-hub-layouts-v2');
    return saved ? JSON.parse(saved) : {};
  });

  // Regenerate layout when agents change
  const currentLayout = layouts.lg?.length >= allAgentNames.length
    ? layouts
    : { lg: generateLayout(allAgentNames), md: generateLayout(allAgentNames), sm: generateLayout(allAgentNames) };

  const handleLayoutChange = useCallback((_layout: any[], allLayouts: Record<string, any[]>) => {
    setLayouts(allLayouts);
    localStorage.setItem('ce-hub-layouts-v2', JSON.stringify(allLayouts));
  }, []);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#0d0d1a' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '6px 16px', background: '#111122', borderBottom: '1px solid #222',
        fontFamily: 'SF Mono, Menlo, monospace', fontSize: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontWeight: 700, color: '#4ade80' }}>ce-hub</span>
          <span style={{ color: connected ? '#4ade80' : '#f87171' }}>
            {connected ? '● connected' : '○ disconnected'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ color: '#555' }}>{allAgentNames.length} agents</span>
          <button onClick={() => setShowSettings(true)}
            style={{ background: '#1a1a2e', color: '#888', border: '1px solid #333', borderRadius: 3, padding: '2px 10px', cursor: 'pointer', fontSize: 11, fontFamily: 'inherit' }}>
            settings
          </button>
        </div>
      </div>

      {/* Grid */}
      <div style={{ flex: 1, overflow: 'auto', padding: 4 }}>
        <ResponsiveGridLayout
          className="layout"
          layouts={currentLayout}
          breakpoints={{ lg: 1200, md: 900, sm: 600 }}
          cols={{ lg: 12, md: 9, sm: 6 }}
          rowHeight={35}
          onLayoutChange={handleLayoutChange}
          compactType="vertical"
          margin={[4, 4]}
        >
          {allAgentNames.map(name => (
            <div key={name}>
              <AgentTile
                name={name}
                messages={messages[name] || []}
                onSend={(content) => sendMessage(name, content)}
                onSubscribe={() => subscribe(name)}
              />
            </div>
          ))}
        </ResponsiveGridLayout>
      </div>

      <SettingsPanel visible={showSettings} onClose={() => setShowSettings(false)} />
    </div>
  );
}
