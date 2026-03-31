import React, { useEffect, useRef } from 'react';
import type { AgentMessage } from '../hooks/useWebSocket';

interface Props {
  messages: AgentMessage[];
}

export function ChatMessages({ messages }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages.length]);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px', fontFamily: 'SF Mono, Menlo, monospace', fontSize: 12 }}>
      {messages.length === 0 && (
        <div style={{ color: '#333', fontSize: 11, textAlign: 'center', marginTop: 16 }}>~</div>
      )}
      {messages.map((msg, i) => (
        <div key={i} style={{ marginBottom: 4 }}>
          <span style={{
            color: msg.role === 'user' ? '#4a6cf7' : msg.role === 'system' ? '#f7b84a' : '#4ade80',
            fontWeight: 600,
          }}>
            {msg.role === 'user' ? '> ' : msg.role === 'system' ? '! ' : '← '}
          </span>
          <span style={{ color: '#ccc', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {msg.content}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
