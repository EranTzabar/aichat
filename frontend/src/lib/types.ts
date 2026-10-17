export type UserRef = { id: number; username: string; display_name: string };
export type GroupRef = { id: number; name: string };
export type Likes = { count: number; users: UserRef[] };
export type LikeStatus = { count: number; liked_by_me: boolean };
export type WorkStatus = "open" | "closed";

export type Me = UserRef & { bio: string; is_admin: boolean; groups: GroupRef[] };
export type Person = UserRef & { online: boolean };

export type AttachmentKind = "image" | "audio" | "video" | "file";
/** A file in a message or work post. Its bytes come from GET /attachments/{id}/file (with the login token). */
export type Attachment = { id: number; filename: string; content_type: string; size: number; kind: AttachmentKind };

export type Message = {
  id: number;
  work_id: number;
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
  replies?: Message[] | null;
};

export type Work = {
  id: number;
  title: string;
  body: string;
  status: WorkStatus;
  created_at: string;
  last_activity_at: string;
  group: GroupRef;
  author: UserRef;
  likes: Likes;
  liked_by_me: boolean;
  attachments: Attachment[];
};

export type WorkState = {
  server_time: string;
  work: Work;
  messages: Message[];
  participants: UserRef[];
};

export type WorkListItem = {
  id: number;
  title: string;
  group_id: number;
  group_name: string;
  status: WorkStatus;
  created_at: string;
  last_activity_at: string;
  message_count: number;
  unread_count: number;
  joined: boolean;
  last_message: { id: number; author: UserRef; body_preview: string; created_at: string } | null;
};

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
  work_count: number;
};
export type GroupDetail = Group & { members: UserRef[] };

/** Events pushed over the WebSocket. */
export type LiveEvent =
  | { type: "hello"; user_id: number; online_user_ids: number[] }
  | { type: "presence.changed"; user_id: number; online: boolean }
  | { type: "message.created"; work_id: number; message: Message }
  | {
      type: "like.changed";
      work_id: number;
      target_type: "work" | "message";
      target_id: number;
      count: number;
      user: UserRef;
      liked: boolean;
    }
  | { type: "message.seen"; work_id: number; user: UserRef; message_ids: number[] }
  | { type: "work.created"; work_id: number; work: Work }
  | { type: "work.updated"; work_id: number; work: Pick<Work, "id" | "title" | "body" | "status" | "attachments"> }
  | { type: "access.revoked"; group_id: number; group_name: string }
  | { type: "group.deleted"; group_id: number; group_name: string }
  | { type: "groups.changed" };
