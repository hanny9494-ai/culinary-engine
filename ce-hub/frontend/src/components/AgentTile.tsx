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

const STATUS_COLORS: Record<string, string> = {
  running: '#4ade80', idle: '#666', stopped: '#666', error: '#f87171',
};

export function AgentTile({ name, messages, onSend, onSubscribe }: Props) {
  useEffect(() => { onSubscribe(); }, [onSubscribe]);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: '#1e1e3a', borderRadius: 8, border: '1px solid #333',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 12px', background: '#16162a', borderBottom: '1px solid #333',
        minHeight: 36,
      }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: messages.length > 0 ? '#4ade80' : '#666',
        }} />
        <span style={{ fontWeight: 600, fontSize: 13 }}>{name}</span>
      </div>
      <ChatMessages messages={messages} />
      <ChatInput onSend={onSend} />
    </div>
  );
}
