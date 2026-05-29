import { useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Phone, PhoneOff, Video, VideoOff } from 'lucide-react';
import { callsApi } from '@/api/endpoints';
import { wsClient } from '@/ws/client';
import type { CallOut } from '@/api/types';
import { useCallsStore } from '@/store/calls';
import { useAuthStore } from '@/store/auth';
import { Avatar } from '@/components/ui/Avatar';

const RTC_CONFIG: RTCConfiguration = {
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
};

export function CallManager() {
  const me = useAuthStore((s) => s.me);
  const incoming = useCallsStore((s) => s.incoming);
  const active = useCallsStore((s) => s.active);
  const setIncoming = useCallsStore((s) => s.setIncoming);
  const setActive = useCallsStore((s) => s.setActive);

  // Подписка на WS события
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event.type === 'call_incoming') {
        const call = event.call as CallOut | undefined;
        if (!call) return;
        if (call.initiator_id === me?.id) return; // мы инициатор
        setIncoming(call);
      } else if (event.type === 'call_accepted') {
        const call = event.call as CallOut | undefined;
        if (call) setActive(call);
      } else if (event.type === 'call_declined' || event.type === 'call_ended') {
        setActive(null);
        setIncoming(null);
      }
    });
    return unsub;
  }, [me?.id, setIncoming, setActive]);

  if (incoming && !active) {
    return <IncomingCall call={incoming} />;
  }
  if (active) {
    return <ActiveCall call={active} />;
  }
  return null;
}

function IncomingCall({ call }: { call: CallOut }) {
  const setIncoming = useCallsStore((s) => s.setIncoming);
  const setActive = useCallsStore((s) => s.setActive);

  const initiator = call.participants.find((p) => p.user_id === call.initiator_id);

  async function accept(): Promise<void> {
    try {
      const c = await callsApi.accept(call.id);
      setIncoming(null);
      setActive(c);
    } catch {
      setIncoming(null);
    }
  }
  async function decline(): Promise<void> {
    await callsApi.decline(call.id).catch(() => {});
    setIncoming(null);
  }

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70">
      <div className="flex w-full max-w-sm flex-col items-center gap-5 rounded-2xl bg-bg p-8 text-center">
        <Avatar
          src={initiator?.avatar_url ?? null}
          name={initiator?.username ?? '?'}
          id={initiator?.user_id ?? 0}
          size={96}
        />
        <div>
          <div className="text-xl font-medium">
            {initiator?.username ? `@${initiator.username}` : 'Incoming call'}
          </div>
          <div className="text-sm text-muted">
            {call.is_video ? 'Video call' : 'Voice call'}
          </div>
        </div>
        <div className="flex w-full justify-around">
          <button
            onClick={decline}
            className="flex h-16 w-16 items-center justify-center rounded-full bg-danger text-white"
            aria-label="Decline"
          >
            <PhoneOff className="h-7 w-7" />
          </button>
          <button
            onClick={accept}
            className="flex h-16 w-16 items-center justify-center rounded-full bg-green-500 text-white"
            aria-label="Accept"
          >
            <Phone className="h-7 w-7" />
          </button>
        </div>
      </div>
    </div>
  );
}

function ActiveCall({ call }: { call: CallOut }) {
  const me = useAuthStore((s) => s.me);
  const setActive = useCallsStore((s) => s.setActive);
  const localRef = useRef<HTMLVideoElement | null>(null);
  const remoteRef = useRef<HTMLVideoElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);

  const [muted, setMuted] = useState(false);
  const [videoOff, setVideoOff] = useState(!call.is_video);

  const otherId =
    call.participants.find((p) => p.user_id !== me?.id)?.user_id ?? null;

  // Setup RTCPeerConnection
  useEffect(() => {
    let cancelled = false;
    const pc = new RTCPeerConnection(RTC_CONFIG);
    pcRef.current = pc;

    pc.ontrack = (e) => {
      if (remoteRef.current && e.streams[0]) {
        remoteRef.current.srcObject = e.streams[0];
      }
    };
    pc.onicecandidate = (e) => {
      if (e.candidate && otherId) {
        callsApi
          .signal(call.id, otherId, { kind: 'ice', candidate: e.candidate.toJSON() })
          .catch(() => {});
      }
    };

    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: call.is_video,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        localStreamRef.current = stream;
        if (localRef.current) localRef.current.srcObject = stream;
        for (const track of stream.getTracks()) pc.addTrack(track, stream);

        // Только инициатор шлёт offer
        if (call.initiator_id === me?.id && otherId) {
          const offer = await pc.createOffer();
          await pc.setLocalDescription(offer);
          await callsApi.signal(call.id, otherId, { kind: 'offer', sdp: offer });
        }
      } catch {
        // noop
      }
    })();

    const unsub = wsClient.subscribe(async (event) => {
      if (event.type !== 'call_signal' || event.call_id !== call.id) return;
      const payload = event.payload as { kind: string; sdp?: RTCSessionDescriptionInit; candidate?: RTCIceCandidateInit };
      try {
        if (payload.kind === 'offer' && payload.sdp) {
          await pc.setRemoteDescription(payload.sdp);
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          if (otherId) await callsApi.signal(call.id, otherId, { kind: 'answer', sdp: answer });
        } else if (payload.kind === 'answer' && payload.sdp) {
          await pc.setRemoteDescription(payload.sdp);
        } else if (payload.kind === 'ice' && payload.candidate) {
          await pc.addIceCandidate(payload.candidate);
        }
      } catch {
        // noop
      }
    });

    return () => {
      cancelled = true;
      unsub();
      pc.close();
      localStreamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [call.id, call.initiator_id, call.is_video, me?.id, otherId]);

  function toggleMute(): void {
    const stream = localStreamRef.current;
    if (!stream) return;
    const next = !muted;
    stream.getAudioTracks().forEach((t) => (t.enabled = !next));
    setMuted(next);
    void callsApi.state(call.id, { is_muted: next }).catch(() => {});
  }
  function toggleVideo(): void {
    const stream = localStreamRef.current;
    if (!stream) return;
    const next = !videoOff;
    stream.getVideoTracks().forEach((t) => (t.enabled = !next));
    setVideoOff(next);
    void callsApi.state(call.id, { is_video_on: !next }).catch(() => {});
  }
  async function hangup(): Promise<void> {
    await callsApi.end(call.id).catch(() => {});
    setActive(null);
  }

  const other = call.participants.find((p) => p.user_id === otherId);

  return (
    <div className="fixed inset-0 z-[200] flex flex-col bg-black text-white">
      <div className="relative flex-1 overflow-hidden">
        <video ref={remoteRef} autoPlay playsInline className="h-full w-full object-cover" />
        {call.is_video && (
          <video
            ref={localRef}
            autoPlay
            playsInline
            muted
            className="absolute right-4 top-4 h-32 w-24 rounded-lg border border-white/30 object-cover sm:h-44 sm:w-32"
          />
        )}
        <div className="absolute left-1/2 top-6 -translate-x-1/2 text-center">
          <div className="text-lg font-medium">
            {other?.username ? `@${other.username}` : 'Call'}
          </div>
          <div className="text-sm opacity-70">
            {call.status === 'ringing' ? 'Ringing…' : 'Connected'}
          </div>
        </div>
      </div>
      <div className="flex justify-around bg-black/80 py-6">
        <button
          onClick={toggleMute}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-white/15"
          aria-label="Mute"
        >
          {muted ? <MicOff className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
        </button>
        {call.is_video && (
          <button
            onClick={toggleVideo}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-white/15"
            aria-label="Camera"
          >
            {videoOff ? <VideoOff className="h-6 w-6" /> : <Video className="h-6 w-6" />}
          </button>
        )}
        <button
          onClick={hangup}
          className="flex h-14 w-14 items-center justify-center rounded-full bg-danger"
          aria-label="Hang up"
        >
          <PhoneOff className="h-6 w-6" />
        </button>
      </div>
    </div>
  );
}
