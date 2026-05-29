import { Image as ImageIcon, X, Upload, Users, UsersRound, Globe, Pin } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { StoryPrivacy } from '@/api/types';
import { mediaApi, storiesApi } from '@/api/endpoints';
import { toast } from '@/components/ui/Toaster';
import { Spinner } from '@/components/ui/Spinner';
import { useQueryClient } from '@tanstack/react-query';

interface Props {
  onClose: () => void;
}

export function StoryEditor({ onClose }: Props) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [caption, setCaption] = useState('');
  const [privacy, setPrivacy] = useState<StoryPrivacy>('everybody');
  const [pinned, setPinned] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Автоматически открываем диалог выбора при первом рендере
  useEffect(() => {
    fileRef.current?.click();
  }, []);

  async function publish(): Promise<void> {
    if (!file) return;
    setUploading(true);
    try {
      const isVideo = file.type.startsWith('video/');
      const up = await mediaApi.uploadStory(file);
      await storiesApi.create({
        media_url: up.file_url,
        media_type: isVideo ? 'video' : 'photo',
        caption: caption || null,
        privacy,
        pinned,
        allow_replies: true,
        allow_reactions: true,
        allow_forwards: true,
        width: up.width,
        height: up.height,
        duration: up.duration,
      });
      toast.success('Story published');
      queryClient.invalidateQueries({ queryKey: ['stories', 'feed'] });
      queryClient.invalidateQueries({ queryKey: ['user-stories'] });
      onClose();
    } catch {
      toast.error('Failed to publish');
    } finally {
      setUploading(false);
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[300] flex items-center justify-center bg-black/95 animate-fade-in">
      <input
        ref={fileRef}
        type="file"
        accept="image/*,video/*"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) setFile(f);
          else onClose();
        }}
      />

      <div className="flex h-full w-full max-w-md flex-col">
        <header className="flex h-14 items-center gap-3 px-3 pt-safe text-white">
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-white/10"
          >
            <X className="h-5 w-5" />
          </button>
          <h2 className="text-base font-medium">New story</h2>
        </header>

        <div className="relative flex flex-1 items-center justify-center">
          {!file && (
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-white/30 px-8 py-10 text-white/70 hover:bg-white/5"
            >
              <ImageIcon className="h-12 w-12" />
              <span>Pick a photo or video</span>
            </button>
          )}
          {preview && file?.type.startsWith('video/') && (
            <video src={preview} controls autoPlay className="max-h-full max-w-full" />
          )}
          {preview && !file?.type.startsWith('video/') && (
            <img src={preview} alt="" className="max-h-full max-w-full object-contain" />
          )}
        </div>

        {file && (
          <div className="space-y-3 bg-black/70 px-4 py-3 pb-safe">
            <input
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              maxLength={2000}
              placeholder="Add a caption…"
              className="h-10 w-full rounded-lg bg-white/10 px-3 text-sm text-white placeholder:text-white/50 outline-none"
            />

            <div className="flex flex-wrap gap-2">
              <PrivacyPill
                active={privacy === 'everybody'}
                icon={<Globe className="h-3.5 w-3.5" />}
                label="Everyone"
                onClick={() => setPrivacy('everybody')}
              />
              <PrivacyPill
                active={privacy === 'contacts'}
                icon={<Users className="h-3.5 w-3.5" />}
                label="Contacts"
                onClick={() => setPrivacy('contacts')}
              />
              <PrivacyPill
                active={privacy === 'close_friends'}
                icon={<UsersRound className="h-3.5 w-3.5" />}
                label="Close Friends"
                onClick={() => setPrivacy('close_friends')}
              />
              <PrivacyPill
                active={pinned}
                icon={<Pin className="h-3.5 w-3.5" />}
                label="Pin to profile"
                onClick={() => setPinned((v) => !v)}
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-1">
              <button
                onClick={onClose}
                className="rounded-full px-4 py-2 text-sm text-white/80 hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={publish}
                disabled={uploading}
                className="flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-sm font-medium text-white hover:bg-accentHover disabled:opacity-60"
              >
                {uploading ? <Spinner className="h-4 w-4" /> : <Upload className="h-4 w-4" />}
                Publish
              </button>
            </div>
          </div>
        )}

        {!file && (
          <div className="px-4 py-2 text-xs text-white/50">
            Pick a file to start
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

function PrivacyPill({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'flex items-center gap-1.5 rounded-full px-3 py-1 text-xs transition-colors ' +
        (active
          ? 'bg-accent text-white'
          : 'bg-white/10 text-white/80 hover:bg-white/20')
      }
    >
      {icon}
      {label}
    </button>
  );
}
