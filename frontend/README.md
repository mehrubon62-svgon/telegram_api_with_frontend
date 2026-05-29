# Telegramm Frontend

Production-grade React + TypeScript + Tailwind client for the Telegramm clone backend.

## Stack

- React 18 + TypeScript (strict)
- Vite
- Tailwind CSS with Telegram-style palette and dark/light theme via CSS variables
- TanStack Query for REST cache + optimistic updates
- Zustand for global state (auth / ui / presence)
- React Router v6 with code-splitting
- Native WebSocket with auto-reconnect + heartbeat
- sonner, lucide-react, date-fns, vaul

## Responsive

- Mobile (< 768px): single panel; chat list and chat view are separate routes
- Tablet (768–1024px): two panels (sidebar + chat)
- Desktop (≥ 1024px): three panels with right info panel
- Uses 100dvh, env(safe-area-inset-*), visualViewport API for keyboards

## Run

Backend must be running on `http://127.0.0.1:8000`.

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

## Generate types from OpenAPI

```bash
npm run gen:types
```

## Notes / TODO

This is the working core. Things wired and operational:

- Login / Register
- Auto-refresh access token (single-flight)
- WebSocket connection with reconnect + heartbeat
- Chat list with WS-driven updates (new message / presence / typing)
- Chat view with messages, input, send/edit/delete via REST + WS push
- Reactions (quick emoji on hover)
- File attachments (photo / video / file) via /media/upload + send
- Drafts (auto-save every 1.5s)
- Settings: theme switch, avatar upload, log out
- Mobile-responsive single panel + back navigation

Things stubbed / left for the next iteration:
- Stories editor / viewer (basic story API ready in `endpoints.ts`)
- Voice recording (MediaRecorder + waveform)
- WebRTC calls UI (signaling endpoints + WS events ready in `endpoints.ts`)
- Polls UI
- Member management screens
- Full emoji picker + GIF / sticker tabs
- Folders tabs
- Read receipts visualization
- Message search overlay (Cmd+K)
- 2FA password verification flow on login

To add any of these, follow the patterns in `MessageBubble`, `MessageInput`, and `endpoints.ts`.
