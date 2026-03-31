import React, { useEffect } from 'react';
import { ChatMessages } from './ChatMessages';
import { ChatInput } from './ChatInput';
import type { AgentMessage } from '../hooks/useWebSocket';

interface Props {
  name: string;
  messages: AgentMessage[];
  onSend: (content: string) => void;
  onSubscribe: () => void;
}

export function AgentTile({ name, messages, onSend, onSubscribe }: Props) {
  useEffect(() => { onSubscribe(); }, [onSubscribe]);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: '#0a0a14', borderRadius: 4, border: '1px solid #1a1a2e',
      overflow: 'hidden', fontFamily: 'SF Mono, Menlo, monospace', fontSize: 12,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '4px 8px', background: '#111122', borderBottom: '1px solid #1a1a2e',
        minHeight: 24, cursor: 'move',
      }} className="drag-handle">
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: messages.length > 0 ? '#4ade80' : '#333',
        }} />
        <span style={{ fontWeight: 600, fontSize: 11, color: '#8888aa' }}>{name}</span>
        {name === 'cc-lead' && <span style={{ fontSize: 9, color: '#4a6cf7', marginLeft: 4 }}>LEAD</span>}
      </div>
      <ChatMessages messages={messages} />
      <ChatInput onSend={onSend} />
    </div>
  );
}
