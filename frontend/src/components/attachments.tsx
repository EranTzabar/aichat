"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  File as FileIcon,
  FileArchive,
  FileSpreadsheet,
  FileText,
  Film,
  LoaderCircle,
  Maximize2,
  Music,
  Play,
  X,
} from "lucide-react";
import { attachmentUrl, downloadAttachment, errorMessage, fileSize, uploadFile } from "@/lib/api";
import type { Attachment } from "@/lib/types";
import { cn } from "@/lib/utils";

// ---------- loading files (they have no public links: each is fetched with the login token) ----------

function useFileUrl(id: number, enabled: boolean) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    attachmentUrl(id).then(
      (u) => alive && setUrl(u),
      (e) => alive && setError(errorMessage(e)),
    );
    return () => {
      alive = false;
    };
  }, [id, enabled]);
  return { url, error, loading: enabled && !url && !error };
}

/** True once the element has scrolled near the screen (so images load only when needed). */
function useVisible<T extends Element>() {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || visible) return;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setVisible(true), { rootMargin: "300px" });
    io.observe(el);
    return () => io.disconnect();
  }, [visible]);
  return { ref, visible };
}

// ---------- display ----------

/** The files of a message or chat post: an image grid, video and audio players, and file cards. */
export function Attachments({ items }: { items: Attachment[] }) {
  const [open, setOpen] = useState<number | null>(null);
  if (items.length === 0) return null;
  const media = items.filter((a) => a.kind === "image" || a.kind === "video");
  const images = items.filter((a) => a.kind === "image");
  const openAt = (a: Attachment) => setOpen(media.findIndex((m) => m.id === a.id));
  return (
    <div className="mt-2 w-full min-w-[240px] space-y-2">
      {images.length > 0 && <ImageGrid images={images} onOpen={openAt} />}
      {items
        .filter((a) => a.kind === "video")
        .map((a) => (
          <VideoPlayer key={a.id} file={a} onExpand={() => openAt(a)} />
        ))}
      {items
        .filter((a) => a.kind === "audio")
        .map((a) => (
          <AudioPlayer key={a.id} file={a} />
        ))}
      {items
        .filter((a) => a.kind === "file")
        .map((a) => (
          <FileCard key={a.id} file={a} />
        ))}
      {open !== null && open >= 0 && <MediaViewer items={media} index={open} onIndex={setOpen} onClose={() => setOpen(null)} />}
    </div>
  );
}

function AuthImage({ file, className, onClick }: { file: Attachment; className?: string; onClick?: () => void }) {
  const { ref, visible } = useVisible<HTMLButtonElement>();
  const { url, error } = useFileUrl(file.id, visible);
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      title={file.filename}
      className={cn("relative block overflow-hidden bg-muted-foreground/10", className)}
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={file.filename} className="size-full object-cover" />
      ) : (
        <span className="flex size-full items-center justify-center p-2 text-xs text-muted-foreground">
          {error ?? <LoaderCircle className="size-5 animate-spin" />}
        </span>
      )}
    </button>
  );
}

function ImageGrid({ images, onOpen }: { images: Attachment[]; onOpen: (a: Attachment) => void }) {
  if (images.length === 1) {
    return (
      <AuthImage
        file={images[0]}
        onClick={() => onOpen(images[0])}
        className="aspect-[4/3] max-h-[420px] w-full rounded-xl"
      />
    );
  }
  if (images.length === 2) {
    return (
      <div className="grid grid-cols-2 gap-1 overflow-hidden rounded-xl">
        {images.map((a) => (
          <AuthImage key={a.id} file={a} onClick={() => onOpen(a)} className="aspect-square w-full" />
        ))}
      </div>
    );
  }
  if (images.length === 3) {
    return (
      <div className="grid h-80 grid-cols-2 grid-rows-2 gap-1 overflow-hidden rounded-xl">
        <AuthImage file={images[0]} onClick={() => onOpen(images[0])} className="row-span-2 size-full" />
        {images.slice(1).map((a) => (
          <AuthImage key={a.id} file={a} onClick={() => onOpen(a)} className="size-full" />
        ))}
      </div>
    );
  }
  const extra = images.length - 4;
  return (
    <div className="grid grid-cols-2 gap-1 overflow-hidden rounded-xl">
      {images.slice(0, 4).map((a, i) => (
        <div key={a.id} className="relative">
          <AuthImage file={a} onClick={() => onOpen(a)} className="aspect-square w-full" />
          {i === 3 && extra > 0 && (
            <button
              type="button"
              onClick={() => onOpen(a)}
              className="absolute inset-0 flex items-center justify-center bg-black/55 text-2xl font-semibold text-white"
            >
              +{extra}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

function VideoPlayer({ file, onExpand }: { file: Attachment; onExpand: () => void }) {
  const [started, setStarted] = useState(false);
  const { url, error, loading } = useFileUrl(file.id, started);
  if (url) {
    return (
      <div className="group relative">
        <video src={url} controls autoPlay playsInline className="max-h-[420px] w-full rounded-xl bg-black" />
        <button
          type="button"
          onClick={onExpand}
          title="Full screen viewer"
          className="absolute top-2 right-2 rounded-full bg-black/60 p-1.5 text-white opacity-0 transition group-hover:opacity-100"
        >
          <Maximize2 className="size-4" />
        </button>
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => setStarted(true)}
      className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl bg-neutral-900 text-white"
    >
      <span className="flex size-14 items-center justify-center rounded-full bg-white/20">
        {loading ? <LoaderCircle className="size-7 animate-spin" /> : <Play className="ml-1 size-7 fill-current" />}
      </span>
      <span className="flex max-w-[90%] items-center gap-1 truncate text-xs opacity-80">
        <Film className="size-3.5 shrink-0" /> {file.filename} · {fileSize(file.size)}
      </span>
      {error && <span className="text-xs text-red-300">{error}</span>}
    </button>
  );
}

function AudioPlayer({ file }: { file: Attachment }) {
  const [started, setStarted] = useState(false);
  const { url, error, loading } = useFileUrl(file.id, started);
  return (
    <div className="rounded-xl border bg-background/60 p-2">
      <div className="flex items-center gap-2">
        {!url && (
          <button
            type="button"
            onClick={() => setStarted(true)}
            title="Play"
            className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"
          >
            {loading ? <LoaderCircle className="size-4 animate-spin" /> : <Play className="ml-0.5 size-4 fill-current" />}
          </button>
        )}
        <Music className={cn("size-4 shrink-0 text-muted-foreground", !url && "hidden")} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{file.filename}</div>
          <div className="text-[11px] text-muted-foreground">{fileSize(file.size)}</div>
        </div>
      </div>
      {url && <audio src={url} controls autoPlay className="mt-2 w-full" />}
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
    </div>
  );
}

function fileIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (["zip", "rar", "7z", "gz", "tar", "bz2"].includes(ext)) return FileArchive;
  if (["xls", "xlsx", "csv", "ods"].includes(ext)) return FileSpreadsheet;
  if (["pdf", "doc", "docx", "txt", "md", "rtf", "odt", "ppt", "pptx"].includes(ext)) return FileText;
  return FileIcon;
}

function FileCard({ file }: { file: Attachment }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const Icon = fileIcon(file.filename);
  async function download() {
    setBusy(true);
    setError(null);
    try {
      await downloadAttachment(file);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex items-center gap-3 rounded-xl border bg-background/60 p-2">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{file.filename}</div>
        <div className="text-[11px] text-muted-foreground">{error ?? fileSize(file.size)}</div>
      </div>
      <button
        type="button"
        onClick={download}
        disabled={busy}
        title="Download"
        className="rounded-full p-2 text-muted-foreground hover:bg-muted hover:text-foreground"
      >
        {busy ? <LoaderCircle className="size-4 animate-spin" /> : <Download className="size-4" />}
      </button>
    </div>
  );
}

/** Full-screen, dark viewer for the images and videos of one message; arrows move, Esc closes. */
function MediaViewer({
  items,
  index,
  onIndex,
  onClose,
}: {
  items: Attachment[];
  index: number;
  onIndex: (i: number) => void;
  onClose: () => void;
}) {
  const file = items[index];
  const { url, error } = useFileUrl(file.id, true);
  const go = useCallback((step: number) => onIndex((index + step + items.length) % items.length), [index, items.length, onIndex]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [go, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black/95 text-white" role="dialog" aria-label={file.filename}>
      <div className="flex items-center gap-3 p-3 text-sm">
        <span className="min-w-0 flex-1 truncate">{file.filename}</span>
        {items.length > 1 && (
          <span className="opacity-70">
            {index + 1} / {items.length}
          </span>
        )}
        <button
          type="button"
          onClick={() => downloadAttachment(file)}
          title="Download"
          className="rounded-full p-2 hover:bg-white/15"
        >
          <Download className="size-5" />
        </button>
        <button type="button" onClick={onClose} title="Close (Esc)" className="rounded-full p-2 hover:bg-white/15">
          <X className="size-5" />
        </button>
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center px-12 pb-6" onClick={onClose}>
        {url ? (
          file.kind === "video" ? (
            <video
              key={file.id}
              src={url}
              controls
              autoPlay
              playsInline
              className="max-h-full max-w-full"
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={url}
              alt={file.filename}
              className="max-h-full max-w-full object-contain"
              onClick={(e) => e.stopPropagation()}
            />
          )
        ) : (
          <span className="text-sm opacity-80">{error ?? <LoaderCircle className="size-8 animate-spin" />}</span>
        )}
        {items.length > 1 && (
          <>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                go(-1);
              }}
              title="Previous"
              className="absolute left-2 rounded-full bg-white/10 p-2 hover:bg-white/25"
            >
              <ChevronLeft className="size-6" />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                go(1);
              }}
              title="Next"
              className="absolute right-2 rounded-full bg-white/10 p-2 hover:bg-white/25"
            >
              <ChevronRight className="size-6" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ---------- uploading ----------

export type Upload = {
  key: string;
  file: File;
  preview: string | null;
  progress: number;
  attachment?: Attachment;
  error?: string;
};

/** Files being attached before sending: each uploads right away. */
export function useUploads(chatId: number) {
  const [items, setItems] = useState<Upload[]>([]);
  const update = (key: string, patch: Partial<Upload>) =>
    setItems((list) => list.map((u) => (u.key === key ? { ...u, ...patch } : u)));

  function add(files: Iterable<File>) {
    for (const file of files) {
      const key = `${Date.now()}-${Math.random()}`;
      const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : null;
      setItems((list) => [...list, { key, file, preview, progress: 0 }]);
      uploadFile(chatId, file, (p) => update(key, { progress: p })).then(
        (attachment) => update(key, { attachment, progress: 1 }),
        (e) => update(key, { error: errorMessage(e) }),
      );
    }
  }

  function remove(key: string) {
    setItems((list) => {
      const gone = list.find((u) => u.key === key);
      if (gone?.preview) URL.revokeObjectURL(gone.preview);
      return list.filter((u) => u.key !== key);
    });
  }

  function clear() {
    setItems((list) => {
      list.forEach((u) => u.preview && URL.revokeObjectURL(u.preview));
      return [];
    });
  }

  return {
    items,
    add,
    remove,
    clear,
    ids: items.flatMap((u) => (u.attachment ? [u.attachment.id] : [])),
    busy: items.some((u) => !u.attachment && !u.error),
  };
}

export function UploadChips({ items, onRemove }: { items: Upload[]; onRemove: (key: string) => void }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((u) => {
        const Icon = u.file.type.startsWith("video/") ? Film : u.file.type.startsWith("audio/") ? Music : fileIcon(u.file.name);
        return (
          <div
            key={u.key}
            className={cn(
              "relative flex w-48 items-center gap-2 overflow-hidden rounded-lg border bg-background p-1.5 pr-7",
              u.error && "border-destructive",
            )}
          >
            {u.preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={u.preview} alt="" className="size-9 shrink-0 rounded object-cover" />
            ) : (
              <span className="flex size-9 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
                <Icon className="size-4" />
              </span>
            )}
            <div className="min-w-0 flex-1 text-xs">
              <div className="truncate font-medium">{u.file.name}</div>
              <div className={cn("truncate text-muted-foreground", u.error && "text-destructive")} title={u.error}>
                {u.error ?? (u.attachment ? fileSize(u.file.size) : `Uploading ${Math.round(u.progress * 100)}%`)}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onRemove(u.key)}
              title="Remove"
              className="absolute top-1 right-1 rounded p-0.5 text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
            {!u.attachment && !u.error && (
              <span className="absolute bottom-0 left-0 h-0.5 bg-primary transition-all" style={{ width: `${u.progress * 100}%` }} />
            )}
          </div>
        );
      })}
    </div>
  );
}
