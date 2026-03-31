import { useEffect, useRef, useCallback, useState } from 'react';

export interface AgentMessage {
  agentName: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<Record<string, AgentMessage[]>>({});
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}`);

    ws.onopen = () => { setConnected(true); console.log('[ws] connected'); };
    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'agent_message' && msg.agentName) {
          setMessages(prev => ({
            ...prev,
            [msg.agentName]: [...(prev[msg.agentName] || []), {
              agentName: msg.agentName, role: msg.role || 'assistant',
              content: msg.content, timestamp: msg.timestamp || Date.now(),
            }],
          }));
        } else if (msg.type === 'task_update') {
          // Could dispatch to task state - for now just log
          console.log('[ws] task update:', msg);
        }
      } catch {}
    };
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); clearTimeout(reconnectTimer.current); };
  }, [connect]);

  const sendMessage = useCallback((agentName: string, content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    // Add user message locally
    setMessages(prev => ({
      ...prev,
      [agentName]: [...(prev[agentName] || []), {
        agentName, role: 'user', content, timestamp: Date.now(),
      }],
    }));
    wsRef.current.send(JSON.stringify({ type: 'send_message', agentName, content }));
  }, []);

  const subscribe = useCallback((agentName: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'subscribe', agentName }));
    }
  }, []);

  return { connected, messages, sendMessage, subscribe };
}
