import { WS_BASE } from '@/lib/url';

type Listener = (event: WSEvent) => void;

export interface WSEvent {
  type: string;
  [key: string]: unknown;
}

const BACKOFF = [1000, 2000, 4000, 8000, 16000, 30000];

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private token = '';
  private listeners = new Set<Listener>();
  private reconnectAttempt = 0;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private explicitlyClosed = false;
  private connectingPromise: Promise<void> | null = null;
  private onReconnectCb: (() => void) | null = null;

  setToken(token: string): void {
    this.token = token;
  }

  onReconnect(cb: () => void): void {
    this.onReconnectCb = cb;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  send(event: WSEvent): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
    }
  }

  isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  async connect(token?: string): Promise<void> {
    if (token) this.token = token;
    if (!this.token) return;
    this.explicitlyClosed = false;
    if (this.connectingPromise) return this.connectingPromise;
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.connectingPromise = new Promise<void>((resolve) => {
      const ws = new WebSocket(`${WS_BASE}/ws?token=${encodeURIComponent(this.token)}`);
      this.ws = ws;
      const wasReconnect = this.reconnectAttempt > 0;

      ws.onopen = () => {
        this.reconnectAttempt = 0;
        this.startHeartbeat();
        if (wasReconnect && this.onReconnectCb) this.onReconnectCb();
        this.connectingPromise = null;
        resolve();
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WSEvent;
          for (const l of this.listeners) l(data);
        } catch {
          // ignore malformed
        }
      };

      ws.onclose = () => {
        this.stopHeartbeat();
        this.ws = null;
        this.connectingPromise = null;
        if (!this.explicitlyClosed) {
          this.scheduleReconnect();
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    });
    return this.connectingPromise;
  }

  disconnect(): void {
    this.explicitlyClosed = true;
    this.stopHeartbeat();
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.explicitlyClosed) return;
    const delay = BACKOFF[Math.min(this.reconnectAttempt, BACKOFF.length - 1)] ?? 30000;
    this.reconnectAttempt += 1;
    setTimeout(() => {
      if (!this.explicitlyClosed) this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeat = setInterval(() => this.send({ type: 'ping' }), 25000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeat) {
      clearInterval(this.heartbeat);
      this.heartbeat = null;
    }
  }
}

export const wsClient = new WebSocketClient();
