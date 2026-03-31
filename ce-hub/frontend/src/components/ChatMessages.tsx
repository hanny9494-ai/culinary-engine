import React, { useEffect, useRef } from 'react';
import type { AgentMessage } from '../hooks/useWebSocket';

interface Props {
  messages: AgentMessage[];
}

export function ChatMessages({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
      {messages.length === 0 && (
        <div style={{ color: '#666', fontSize: 13, textAlign: 'center', marginTop: 20 }}>
          No messages yet
        </div>
      )}
      {messages.map((msg, i) => (
        <div key={i} style={{ marginBottom: 8, display: 'flex', flexDirection: 'column' }}>
          <div style={{
            fontSize: 11, fontWeight: 600, marginBottom: 2,
            color: msg.role === 'user' ? '#4a6cf7' : msg.role === 'system' ? '#f7b84a' : '#6cf74a',
          }}>
            {msg.role === 'user' ? 'You' : msg.role === 'system' ? 'System' : msg.agentName}
          </div>
          <div style={{
            fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            background: msg.role === 'user' ? '#252560' : '#1e1e3a',
            padding: '6px 10px', borderRadius: 6, maxWidth: '95%',
          }}>
            {msg.content}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
