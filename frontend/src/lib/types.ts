export type UserRef = { id: number; username: string; display_name: string };
export type GroupRef = { id: number; name: string };
export type Likes = { count: number; users: UserRef[] };
export type LikeStatus = { count: number; liked_by_me: boolean };
export type ChatStatus = "open" | "closed";

export type Me = UserRef & { bio: string; is_admin: boolean; groups: GroupRef[] };
export type Person = UserRef & { online: boolean; active: boolean };

export type AttachmentKind = "image" | "audio" | "video" | "file";
/** A file in a message or chat post. Its bytes come from GET /attachments/{id}/file (with the login token). */
export type Attachment = { id: number; filename: string; content_type: string; size: number; kind: AttachmentKind };

export type Message = {
  id: number;
  chat_id: number;
  parent_id: number | null;
  body: string;
  created_at: string;
  author: UserRef;
  reply_to: UserRef | null;
  likes: Likes;
  liked_by_me: boolean;
  /** Users whose AI agent read this message through the MCP (admins are never listed). */
  seen_by: UserRef[];
  attachments: Attachment[];
  /** Users tagged in the body: `<@id>` or `@username`. */
  mentions?: UserRef[];
  replies?: Message[] | null;
};

export type Chat = {
  id: number;
  title: string;
  body: string;
  status: ChatStatus;
  created_at: string;
  last_activity_at: string;
  group: GroupRef;
  author: UserRef;
  likes: Likes;
  liked_by_me: boolean;
  attachments: Attachment[];
  mentions?: UserRef[];
  /** People/AIs picked to be notified about the chat. */
  tagged: UserRef[];
  repeat: Repeat | null;
  next_copy_at: string | null;
  close_at: string | null;
  /** For a copy of a repeating chat: the chat it repeats. */
  series: ChatRef | null;
  /** For a repeating chat: its latest copies, newest first. */
  copies: ChatRef[];
};

export type ChatRef = { id: number; title: string };
/** Opens a copy "<title> – <date>" every day or week at `time` (server time zone); the previous copy closes. */
export type Repeat = {
  every: "daily" | "weekly";
  /** 0 = Monday … 6 = Sunday (weekly only). */
  weekday?: number;
  time: string;
  close_after_days?: number;
};

export type ChatState = {
  server_time: string;
  chat: Chat;
  messages: Message[];
  participants: UserRef[];
};

export type ChatListItem = {
  id: number;
  title: string;
  group_id: number;
  group_name: string;
  status: ChatStatus;
  created_at: string;
  last_activity_at: string;
  message_count: number;
  unread_count: number;
  /** Unread messages that tag me. */
  unread_mentions: number;
  joined: boolean;
  last_message: { id: number; author: UserRef; body_preview: string; created_at: string } | null;
  repeat: Repeat | null;
  next_copy_at: string | null;
  close_at: string | null;
};

export type SearchType = "all" | "chats" | "messages" | "files";
/** One hit of GET /search. Matched words in `snippet` are wrapped in « and ». */
export type SearchHit = {
  type: "chat" | "message" | "file";
  chat_id: number;
  chat_title: string;
  group: GroupRef;
  message_id: number | null;
  attachment: Attachment | null;
  author: UserRef;
  created_at: string;
  snippet: string;
};
export type SearchResults = { total: number; results: SearchHit[] };

export type AuditVia = "web" | "api" | "auto";
/** One row of GET /admin/audit. `chat` is null when the chat was deleted (`chat_id` stays). */
export type AuditEvent = {
  id: number;
  at: string;
  actor: UserRef | null;
  via: AuditVia;
  action: string;
  target_type: string | null;
  target_id: number | null;
  chat: { id: number; title: string } | null;
  chat_id: number | null;
  group: GroupRef | null;
  details: Record<string, unknown>;
  ip: string | null;
};
export type AuditPage = { events: AuditEvent[]; next_before_id: number | null };

export type AdminUser = {
  id: number;
  username: string;
  display_name: string;
  bio: string;
  is_admin: boolean;
  is_active: boolean;
  api_enabled: boolean;
  created_at: string;
  last_login_at: string | null;
  last_api_use_at: string | null;
  groups: GroupRef[];
};

export type ApiToken = { user_id: number; token: string; token_version: number; api_enabled: boolean };

export type Group = {
  id: number;
  name: string;
  description: string;
  created_at: string;
  member_count: number;
  chat_count: number;
};
export type GroupDetail = Group & { members: UserRef[] };

/** Events pushed over the WebSocket. */
export type LiveEvent =
  | { type: "hello"; user_id: number; online_user_ids: number[] }
  | { type: "presence.changed"; user_id: number; online: boolean }
  | { type: "message.created"; chat_id: number; message: Message }
  | {
      type: "like.changed";
      chat_id: number;
      target_type: "chat" | "message";
      target_id: number;
      count: number;
      user: UserRef;
      liked: boolean;
    }
  | { type: "message.seen"; chat_id: number; user: UserRef; message_ids: number[] }
  | { type: "chat.created"; chat_id: number; chat: Chat }
  | {
      type: "chat.updated";
      chat_id: number;
      chat: Pick<Chat, "id" | "title" | "body" | "status" | "attachments"> &
        Partial<Pick<Chat, "mentions" | "tagged" | "repeat" | "next_copy_at" | "close_at">>;
    }
  | { type: "access.revoked"; group_id: number; group_name: string }
  | { type: "group.deleted"; group_id: number; group_name: string }
  | { type: "groups.changed" };
