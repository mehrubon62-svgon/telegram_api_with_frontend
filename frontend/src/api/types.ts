// Типы соответствуют схемам бэкенда.
// При необходимости можно перегенерировать через `npm run gen:types`
// (openapi-typescript) при запущенном бэкенде.

export type Platform = 'web' | 'android' | 'ios' | 'desktop';
export type Role = 'user' | 'admin';

export type ChatType = 'private' | 'group' | 'supergroup' | 'channel' | 'saved' | 'secret';
export type ChatMemberRole = 'creator' | 'admin' | 'member' | 'restricted' | 'left' | 'banned';
export type MessageType =
  | 'text'
  | 'photo'
  | 'video'
  | 'video_note'
  | 'animation'
  | 'audio'
  | 'voice'
  | 'file'
  | 'location'
  | 'live_location'
  | 'contact'
  | 'poll'
  | 'call'
  | 'story_reply'
  | 'bot_inline'
  | 'system';

export type PrivacyLevel = 'everybody' | 'contacts' | 'nobody';
export type StoryPrivacy = 'everybody' | 'contacts' | 'close_friends' | 'selected';

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserPublic {
  id: number;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  is_verified: boolean;
  is_bot: boolean;
  is_online: boolean;
  last_seen: string;
  name_color: number;
  birthday?: string | null;
}

export interface UserMe extends UserPublic {
  email: string;
  phone: string | null;
  language_code: string;
  theme: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface CommonGroupOut {
  id: number;
  title: string | null;
  public_username: string | null;
  avatar_url: string | null;
  members_count: number;
}

export interface UserProfileOut extends UserPublic {
  is_contact: boolean;
  is_blocked: boolean;
  common_chats: CommonGroupOut[];
}
export interface SessionOut {
  id: number;
  platform: Platform;
  device_name: string | null;
  app_version: string | null;
  ip_address: string | null;
  country: string | null;
  city: string | null;
  is_current: boolean;
  last_active_at: string;
  created_at: string;
  expires_at: string;
}

export interface PrivacyOut {
  last_seen: PrivacyLevel;
  profile_photo: PrivacyLevel;
  phone_number: PrivacyLevel;
  forwards: PrivacyLevel;
  calls: PrivacyLevel;
  groups_invite: PrivacyLevel;
  birthday: PrivacyLevel;
  bio: PrivacyLevel;
}

export interface ChatPermissions {
  can_send_messages: boolean;
  can_send_media: boolean;
  can_send_polls: boolean;
  can_add_users: boolean;
  can_pin_messages: boolean;
  can_change_info: boolean;
}

export interface ChatPeer {
  id: number;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  is_online: boolean;
  last_seen: string | null;
}

export interface ChatOut {
  id: number;
  type: ChatType;
  title: string | null;
  description: string | null;
  avatar_url: string | null;
  public_username: string | null;
  creator_id: number | null;
  peer: ChatPeer | null;
  pinned_message_id: number | null;
  last_message_id: number | null;
  linked_chat_id: number | null;
  is_forum: boolean;
  slow_mode_seconds: number;
  is_history_visible: boolean;
  is_join_by_request: boolean;
  members_count: number;
  permissions: ChatPermissions;
  created_at: string;
}

export interface ChatListItem {
  chat: ChatOut;
  is_pinned: boolean;
  is_archived: boolean;
  is_muted: boolean;
  unread_count: number;
  unread_mentions_count: number;
  last_read_message_id: number | null;
  last_message: {
    id: number;
    type: MessageType;
    text: string;
    sender_id: number | null;
    sender_username: string | null;
    created_at: string | null;
    is_deleted: boolean;
  } | null;
}

export interface MemberOut {
  user_id: number;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  role: ChatMemberRole;
  custom_title: string | null;
  is_muted: boolean;
  joined_at: string;
  can_send_messages: boolean;
  can_send_media: boolean;
  restricted_until: string | null;
}

export interface AttachmentOut {
  id: number;
  file_url: string;
  thumbnail_url: string | null;
  file_name: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  waveform: number[] | null;
  caption: string | null;
  has_spoiler: boolean;
  is_view_once: boolean;
  position: number;
}

export interface SenderOut {
  id: number;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  name_color: number;
}

export interface ForwardOriginOut {
  from_user_id: number | null;
  from_chat_id: number | null;
  from_message_id: number | null;
  sender_name: string | null;
  date: string | null;
}

export interface MessageOut {
  id: number;
  chat_id: number;
  topic_id: number | null;
  sender: SenderOut | null;
  type: MessageType;
  text: string | null;
  entities: Record<string, unknown>[] | null;
  reply_to_id: number | null;
  thread_root_id: number | null;
  reply_quote_text: string | null;
  reply_quote_offset: number | null;
  reply_quote_entities: Record<string, unknown>[] | null;
  forward: ForwardOriginOut | null;
  is_edited: boolean;
  is_deleted: boolean;
  is_pinned: boolean;
  is_silent: boolean;
  is_via_bot: boolean;
  via_bot_id: number | null;
  views_count: number;
  forwards_count: number;
  self_destruct_seconds: number | null;
  expires_at: string | null;
  scheduled_at: string | null;
  is_scheduled: boolean;
  original_language: string | null;
  reply_markup: Record<string, unknown> | null;
  attachments: AttachmentOut[];
  reactions: ReactionEntry[];
  created_at: string;
  edited_at: string | null;
}

export interface ReactionEntry {
  emoji: string;
  count: number;
  chosen: boolean;
  user_ids: number[];
}

export interface UploadOut {
  file_url: string;
  thumbnail_url: string | null;
  file_name: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  waveform: number[] | null;
}

export interface NotificationOut {
  id: number;
  type: string;
  chat_id: number | null;
  message_id: number | null;
  payload: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
}

export interface StoryAuthor {
  id: number;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
}

export interface StoryOut {
  id: number;
  author: StoryAuthor;
  chat_id: number | null;
  media_url: string;
  thumbnail_url: string | null;
  media_type: string;
  duration: number | null;
  width: number | null;
  height: number | null;
  caption: string | null;
  privacy: StoryPrivacy;
  pinned: boolean;
  allow_replies: boolean;
  allow_reactions: boolean;
  allow_forwards: boolean;
  views_count: number;
  reactions_count: number;
  is_viewed: boolean;
  my_reaction: string | null;
  expires_at: string;
  created_at: string;
}

export interface StoryFeedItem {
  author: StoryAuthor;
  has_unviewed: boolean;
  stories: StoryOut[];
}

export type CallType = 'audio' | 'video';
export type CallStatus = 'ringing' | 'accepted' | 'declined' | 'missed' | 'ended';

export interface CallParticipantOut {
  user_id: number;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  joined_at: string | null;
  left_at: string | null;
  is_muted: boolean;
  is_video_on: boolean;
  is_screen_sharing: boolean;
}

export interface CallOut {
  id: number;
  chat_id: number | null;
  initiator_id: number | null;
  type: CallType;
  status: CallStatus;
  is_video: boolean;
  is_group: boolean;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  end_reason: string | null;
  participants: CallParticipantOut[];
}
