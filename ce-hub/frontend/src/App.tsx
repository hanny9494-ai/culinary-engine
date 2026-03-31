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

const DEFAULT_LAYOUT = [
  { i: 'cc-lead',    x: 0, y: 0, w: 6, h: 12, minW: 3, minH: 4 },
  { i: 'coder',      x: 6, y: 0, w: 3, h: 6,  minW: 3, minH: 4 },
  { i: 'researcher', x: 9, y: 0, w: 3, h: 6,  minW: 3, minH: 4 },
  { i: 'pipeline-runner', x: 6, y: 6, w: 3, h: 6, minW: 3, minH: 4 },
  { i: 'architect',  x: 9, y: 6, w: 3, h: 6,  minW: 3, minH: 4 },
];

export default function App() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [layouts, setLayouts] = useState<Record<string, any[]>>(() => {
    const saved = localStorage.getItem('ce-hub-layouts');
    return saved ? JSON.parse(saved) : { lg: DEFAULT_LAYOUT };
  });
  const { connected, messages, sendMessage, subscribe } = useWebSocket();

  useEffect(() => {
    fetch('/api/agents')
      .then(r => r.json())
      .then(data => setAgents(Array.isArray(data) ? data : []))
      .catch(() => {});
  }, []);

  const handleLayoutChange = useCallback((_layout: any[], allLayouts: Record<string, any[]>) => {
    setLayouts(allLayouts);
    localStorage.setItem('ce-hub-layouts', JSON.stringify(allLayouts));
  }, []);

  const visibleAgents = agents.length > 0
    ? agents.filter(a => DEFAULT_LAYOUT.some(l => l.i === a.name) || messages[a.name]?.length)
    : DEFAULT_LAYOUT.map(l => ({ name: l.i, model: '', description: '' }));

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '8px 16px', background: '#16162a', borderBottom: '1px solid #333',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 700, fontSize: 16 }}>ce-hub</span>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: connected ? '#4ade80' : '#f87171',
          }} />
          <span style={{ fontSize: 12, color: '#666' }}>
            {connected ? 'connected' : 'disconnected'}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span style={{ fontSize: 12, color: '#666' }}>{agents.length} agents</span>
          <button
            onClick={() => setShowSettings(true)}
            style={{
              background: '#252545', color: '#e0e0e0', border: '1px solid #444',
              borderRadius: 4, padding: '4px 12px', cursor: 'pointer', fontSize: 12,
            }}
          >Settings</button>
        </div>
      </div>

      {/* Grid */}
      <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
        <ResponsiveGridLayout
          className="layout"
          layouts={layouts}
          breakpoints={{ lg: 1200, md: 900, sm: 600 }}
          cols={{ lg: 12, md: 9, sm: 6 }}
          rowHeight={40}
          onLayoutChange={handleLayoutChange}
          draggableHandle=".drag-handle"
          compactType="vertical"
        >
          {visibleAgents.map(agent => (
            <div key={agent.name}>
              <AgentTile
                name={agent.name}
                messages={messages[agent.name] || []}
                onSend={(content) => sendMessage(agent.name, content)}
                onSubscribe={() => subscribe(agent.name)}
              />
            </div>
          ))}
        </ResponsiveGridLayout>
      </div>

      {/* Settings Panel */}
      <SettingsPanel visible={showSettings} onClose={() => setShowSettings(false)} />
    </div>
  );
}
