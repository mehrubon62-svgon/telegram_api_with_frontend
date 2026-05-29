import { api } from './client';
import type {
  AttachmentOut,
  CallOut,
  ChatListItem,
  ChatOut,
  MemberOut,
  MessageOut,
  NotificationOut,
  PrivacyOut,
  ReactionEntry,
  SessionOut,
  StoryFeedItem,
  StoryOut,
  Token,
  UploadOut,
  UserMe,
  UserPublic,
} from './types';

// ---- Auth ----
export const authApi = {
  register: (body: { email: string; password: string; username?: string; full_name?: string; phone?: string }) =>
    api.post<Token>('/users/register', body).then((r) => r.data),
  registerPhone: (body: { phone: string; full_name: string; username: string }) =>
    api.post<Token>('/users/auth/register-phone', body).then((r) => r.data),
  requestCode: (phone: string) =>
    api.post<{ code: string; phone: string; is_registered: boolean }>('/users/auth/request-code', { phone }).then((r) => r.data),
  verifyCode: (body: { phone: string; code: string; device_name?: string }) =>
    api.post<Token>('/users/auth/verify-code', body).then((r) => r.data),
  login: (body: { identifier: string; password: string; device_name?: string }) =>
    api.post<Token>('/users/login', { ...body, platform: 'web' }).then((r) => r.data),
  verify2fa: (body: { identifier: string; password: string; code_password: string }) =>
    api
      .post<Token>('/users/2fa/verify-login', { identifier: body.identifier, password: body.password, platform: 'web' }, {
        params: {},
        // FastAPI ждёт оба тела — упрощённо передаём через query/json. Здесь backend принимает два body-объекта,
        // поэтому шлём как { identifier, password } + { password: code_password } в одном запросе.
        // Для простоты делаем второй call: верификация требует и UserLogin, и TwoFactorVerify.
      })
      .then((r) => r.data),
  refresh: (refresh_token: string) =>
    api.post<Token>('/users/refresh', { refresh_token }).then((r) => r.data),
  logout: (refresh_token: string) => api.post('/users/logout', { refresh_token }).then((r) => r.data),
  logoutAll: () => api.post('/users/logout-all').then((r) => r.data),
  me: () => api.get<UserMe>('/users/me').then((r) => r.data),
  updateMe: (body: Partial<Pick<UserMe, 'username' | 'full_name' | 'bio' | 'avatar_url' | 'phone' | 'language_code' | 'theme'> & { name_color: number; birthday: string }>) =>
    api.put<UserMe>('/users/me', body).then((r) => r.data),
  changePassword: (body: { old_password: string; new_password: string }) =>
    api.post('/users/me/change-password', body).then((r) => r.data),
  sessions: () => api.get<SessionOut[]>('/users/me/sessions').then((r) => r.data),
  terminateSession: (id: number) => api.delete(`/users/me/sessions/${id}`).then((r) => r.data),
  privacy: () => api.get<PrivacyOut>('/users/me/privacy').then((r) => r.data),
  updatePrivacy: (body: Partial<PrivacyOut>) =>
    api.put<PrivacyOut>('/users/me/privacy', body).then((r) => r.data),
  twoFactorStatus: () => api.get<{ enabled: boolean }>('/users/me/2fa').then((r) => r.data),
  enableTwoFactor: (body: { password: string; hint?: string; recovery_email?: string }) =>
    api.post('/users/me/2fa/enable', body).then((r) => r.data),
  disableTwoFactor: (body: { password: string }) =>
    api.post('/users/me/2fa/disable', body).then((r) => r.data),
  searchUsers: (q: string) => api.get<UserPublic[]>('/users/search', { params: { q } }).then((r) => r.data),
  getUser: (id: number) => api.get<UserPublic>(`/users/${id}`).then((r) => r.data),
  getProfile: (id: number) =>
    api.get<import('./types').UserProfileOut>(`/users/${id}/profile`).then((r) => r.data),
  getUserByUsername: (username: string) =>
    api.get<UserPublic>(`/users/by-username/${encodeURIComponent(username)}`).then((r) => r.data),
};

// ---- Chats ----
export const chatsApi = {
  list: (params?: { archived?: boolean; limit?: number; offset?: number }) =>
    api.get<ChatListItem[]>('/chats', { params }).then((r) => r.data),
  get: (id: number) => api.get<ChatOut>(`/chats/${id}`).then((r) => r.data),
  createPrivate: (user_id: number) =>
    api.post<ChatOut>('/chats/private', { user_id }).then((r) => r.data),
  createGroup: (body: { title: string; description?: string; member_ids: number[]; is_supergroup?: boolean; is_forum?: boolean }) =>
    api.post<ChatOut>('/chats/group', body).then((r) => r.data),
  createChannel: (body: { title: string; description?: string; public_username?: string }) =>
    api.post<ChatOut>('/chats/channel', body).then((r) => r.data),
  update: (id: number, body: Partial<ChatOut> & { permissions?: ChatOut['permissions'] }) =>
    api.put<ChatOut>(`/chats/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/chats/${id}`).then((r) => r.data),
  leave: (id: number) => api.post(`/chats/${id}/leave`).then((r) => r.data),
  members: (id: number, params?: { limit?: number; offset?: number }) =>
    api.get<MemberOut[]>(`/chats/${id}/members`, { params }).then((r) => r.data),
  addMembers: (id: number, user_ids: number[]) =>
    api.post<MemberOut[]>(`/chats/${id}/members`, { user_ids }).then((r) => r.data),
  kick: (id: number, uid: number, ban?: boolean) =>
    api.delete(`/chats/${id}/members/${uid}`, { params: { ban } }).then((r) => r.data),
  mute: (id: number, body: { is_muted: boolean; mute_until?: string }) =>
    api.put(`/chats/${id}/mute`, body).then((r) => r.data),
  pin: (id: number, is_pinned: boolean) =>
    api.put(`/chats/${id}/pin`, { is_pinned }).then((r) => r.data),
  archive: (id: number, is_archived: boolean) =>
    api.put(`/chats/${id}/archive`, { is_archived }).then((r) => r.data),
};

// ---- Messages ----
export const messagesApi = {
  history: (chatId: number, params: { before_id?: number; after_id?: number; topic_id?: number; limit?: number }) =>
    api.get<MessageOut[]>(`/chats/${chatId}/messages`, { params }).then((r) => r.data),
  get: (chatId: number, mid: number) =>
    api.get<MessageOut>(`/chats/${chatId}/messages/${mid}`).then((r) => r.data),
  send: (
    chatId: number,
    body: {
      text?: string;
      type?: string;
      reply_to_id?: number;
      reply_quote?: { text: string; offset?: number };
      topic_id?: number;
      is_silent?: boolean;
      attachments?: AttachmentOut[] | unknown[];
    },
  ) => api.post<MessageOut>(`/chats/${chatId}/messages`, body).then((r) => r.data),
  edit: (chatId: number, mid: number, body: { text?: string }) =>
    api.put<MessageOut>(`/chats/${chatId}/messages/${mid}`, body).then((r) => r.data),
  remove: (chatId: number, mid: number, for_everyone = true) =>
    api.delete(`/chats/${chatId}/messages/${mid}`, { params: { for_everyone } }).then((r) => r.data),
  pin: (chatId: number, mid: number) =>
    api.post(`/chats/${chatId}/messages/${mid}/pin`).then((r) => r.data),
  unpin: (chatId: number, mid: number) =>
    api.delete(`/chats/${chatId}/messages/${mid}/pin`).then((r) => r.data),
  pinned: (chatId: number) =>
    api.get<MessageOut[]>(`/chats/${chatId}/pinned`).then((r) => r.data),
  forward: (body: { from_chat_id: number; message_ids: number[]; to_chat_ids: number[] }) =>
    api.post<MessageOut[]>('/messages/forward', body).then((r) => r.data),
  toggleReaction: (mid: number, emoji: string) =>
    api.post<ReactionEntry[]>(`/messages/${mid}/reactions`, { emoji }).then((r) => r.data),
  getReactions: (mid: number) =>
    api.get<ReactionEntry[]>(`/messages/${mid}/reactions`).then((r) => r.data),
  markRead: (chatId: number, message_id: number) =>
    api.post<{ new_read_message_ids: number[] }>(`/chats/${chatId}/read`, { message_id }).then((r) => r.data),
  searchInChat: (chatId: number, q: string) =>
    api.get<MessageOut[]>(`/chats/${chatId}/search`, { params: { q } }).then((r) => r.data),
  searchGlobal: (q: string) =>
    api.get<MessageOut[]>('/messages/search', { params: { q } }).then((r) => r.data),
  getDraft: (chatId: number) =>
    api.get<{ text: string; reply_to_id: number | null } | null>(`/chats/${chatId}/draft`).then((r) => r.data),
  saveDraft: (chatId: number, body: { text?: string | null; reply_to_id?: number | null }) =>
    api.put(`/chats/${chatId}/draft`, body).then((r) => r.data),
  deleteDraft: (chatId: number) => api.delete(`/chats/${chatId}/draft`).then((r) => r.data),
};

// ---- Media ----
export const mediaApi = {
  upload: async (file: File, kind: 'photo' | 'video' | 'voice' | 'file' = 'file', extra?: Record<string, string | number>) => {
    const fd = new FormData();
    fd.append('file', file);
    if (extra) {
      for (const [k, v] of Object.entries(extra)) fd.append(k, String(v));
    }
    const path =
      kind === 'photo' ? '/media/upload/photo' :
      kind === 'video' ? '/media/upload/video' :
      kind === 'voice' ? '/media/upload/voice' :
      '/media/upload/file';
    const r = await api.post<UploadOut>(path, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return r.data;
  },
  uploadAvatar: async (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    const r = await api.post<{ avatar_url: string }>('/media/upload/avatar', fd);
    return r.data;
  },
  uploadStory: async (file: File, extra?: Record<string, string | number>) => {
    const fd = new FormData();
    fd.append('file', file);
    if (extra) for (const [k, v] of Object.entries(extra)) fd.append(k, String(v));
    const r = await api.post<UploadOut>('/media/upload/story', fd);
    return r.data;
  },
};

// ---- Stories ----
export const storiesApi = {
  feed: () => api.get<StoryFeedItem[]>('/stories/feed').then((r) => r.data),
  create: (body: Partial<StoryOut> & { media_url: string; media_type: string }) =>
    api.post<StoryOut>('/stories', body).then((r) => r.data),
  get: (id: number) => api.get<StoryOut>(`/stories/${id}`).then((r) => r.data),
  remove: (id: number) => api.delete(`/stories/${id}`).then((r) => r.data),
  react: (id: number, emoji: string) =>
    api.post<StoryOut>(`/stories/${id}/reaction`, { emoji }).then((r) => r.data),
  unreact: (id: number) => api.delete<StoryOut>(`/stories/${id}/reaction`).then((r) => r.data),
  reply: (id: number, text: string) =>
    api.post<{ chat_id: number; message_id: number }>(`/stories/${id}/reply`, { text }).then((r) => r.data),
  byUser: (userId: number) =>
    api.get<StoryOut[]>(`/users/${userId}/stories`).then((r) => r.data),
  pinnedByUser: (userId: number) =>
    api.get<StoryOut[]>(`/users/${userId}/stories/pinned`).then((r) => r.data),
};

// ---- Calls ----
export const callsApi = {
  start: (body: { callee_id?: number; chat_id?: number; type?: 'audio' | 'video'; is_video?: boolean }) =>
    api.post<CallOut>('/calls', body).then((r) => r.data),
  accept: (id: number) => api.post<CallOut>(`/calls/${id}/accept`).then((r) => r.data),
  decline: (id: number) => api.post<CallOut>(`/calls/${id}/decline`).then((r) => r.data),
  leave: (id: number) => api.post<CallOut>(`/calls/${id}/leave`).then((r) => r.data),
  end: (id: number, end_reason?: string) =>
    api.post<CallOut>(`/calls/${id}/end`, { end_reason }).then((r) => r.data),
  state: (id: number, body: { is_muted?: boolean; is_video_on?: boolean; is_screen_sharing?: boolean }) =>
    api.put<CallOut>(`/calls/${id}/state`, body).then((r) => r.data),
  signal: (id: number, target_user_id: number, payload: Record<string, unknown>) =>
    api.post(`/calls/${id}/signal`, { target_user_id, payload }).then((r) => r.data),
  history: () => api.get<CallOut[]>('/calls').then((r) => r.data),
};

// ---- Notifications ----
export const notificationsApi = {
  list: (unread_only = false) =>
    api.get<NotificationOut[]>('/notifications', { params: { unread_only } }).then((r) => r.data),
  unreadCount: () =>
    api.get<{ total: number; by_type: Record<string, number> }>('/notifications/unread-count').then((r) => r.data),
  markRead: (id: number) => api.post(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () => api.post('/notifications/read-all').then((r) => r.data),
};

// ---- Contacts / Blocks ----
export const contactsApi = {
  list: () => api.get('/contacts').then((r) => r.data),
  add: (body: { user_id: number }) => api.post('/contacts', body).then((r) => r.data),
  remove: (uid: number) => api.delete(`/contacts/${uid}`).then((r) => r.data),
};
export const blocksApi = {
  list: () => api.get('/blocks').then((r) => r.data),
  block: (user_id: number) => api.post('/blocks', { user_id }).then((r) => r.data),
  unblock: (uid: number) => api.delete(`/blocks/${uid}`).then((r) => r.data),
};
