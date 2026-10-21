"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Avatar } from "@/components/avatar";
import { MENTION_CLASS } from "@/components/mention";
import { indexPeople, resolveTag, tag, TAG_RE, usePeople } from "@/lib/people";
import type { Person, UserRef } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_SUGGESTIONS = 8;
// Text right before the caret that opens the list: "@" plus what was typed after it.
const QUERY_RE = /(?:^|[^\w@<])@([^\s@<>]{0,30})$/;
// A finished "@username" right before the character just typed.
const TYPED_TAG_RE = /(?:^|[^\w@<])@([A-Za-z0-9_.-]+)$/;

type Suggest = { node: Text; start: number; query: string; top: number; left: number; above: boolean };

function chip(user: UserRef): HTMLSpanElement {
  const span = document.createElement("span");
  span.dataset.uid = String(user.id);
  span.dataset.name = user.display_name;
  span.className = MENTION_CLASS;
  span.title = `@${user.username}`;
  span.textContent = user.display_name;
  return span;
}

/** The editor's text, with chips as `<@id>`. A last <br> is only the browser's placeholder for an empty line. */
function serialize(root: HTMLElement): string {
  let out = "";
  const walk = (node: Node) => {
    node.childNodes.forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) out += (child.textContent ?? "").replace(/ /g, " ");
      else if (child instanceof HTMLBRElement) {
        if (!(child === root.lastChild)) out += "\n";
      } else if (child instanceof HTMLElement && child.dataset.uid) out += tag(Number(child.dataset.uid));
      else if (child instanceof HTMLElement) {
        if ((child.tagName === "DIV" || child.tagName === "P") && out && !out.endsWith("\n")) out += "\n";
        walk(child);
      }
    });
  };
  walk(root);
  return out;
}

/** Fill the editor from text: tags of known users become chips, new lines become <br>. */
function render(root: HTMLElement, value: string, find: (id?: string, name?: string) => UserRef | null) {
  root.replaceChildren();
  const addText = (text: string) =>
    text.split("\n").forEach((line, i) => {
      if (i > 0) root.append(document.createElement("br"));
      if (line) root.append(document.createTextNode(line));
    });
  let last = 0;
  for (const m of value.matchAll(TAG_RE)) {
    const user = find(m[1], m[2]);
    // Only an exact @username becomes a chip here (not "@dana." with its dot).
    if (!user || (m[2] && m[2].toLowerCase() !== user.username.toLowerCase())) continue;
    addText(value.slice(last, m.index));
    root.append(chip(user));
    last = m.index + m[0].length;
  }
  addText(value.slice(last));
  if (value.endsWith("\n")) root.append(document.createElement("br"));
}

function placeCaret(node: Node, offset: number) {
  const sel = window.getSelection();
  if (!sel) return;
  const range = document.createRange();
  range.setStart(node, offset);
  range.collapse(true);
  sel.removeAllRanges();
  sel.addRange(range);
}

function caretAtEnd(root: HTMLElement) {
  const range = document.createRange();
  range.selectNodeContents(root);
  range.collapse(false);
  const sel = window.getSelection();
  sel?.removeAllRanges();
  sel?.addRange(range);
}

function matchesQuery(p: Person, q: string): boolean {
  if (!q) return true;
  const lower = q.toLowerCase();
  return (
    p.username.toLowerCase().startsWith(lower) ||
    p.display_name.toLowerCase().split(/\s+/).some((w) => w.startsWith(lower)) ||
    p.display_name.toLowerCase().startsWith(lower)
  );
}

/**
 * A text box where "@" opens a list of people. A picked person shows as their name in blue (without the @) and
 * is stored as `<@id>`, so people with the same name stay apart. Typing a real "@username" turns blue too.
 * Editing a blue name turns it back into plain "@text".
 */
export function MentionInput({
  value,
  onChange,
  placeholder,
  autoFocus,
  id,
  className,
  onKeyDown,
  onPaste,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  id?: string;
  className?: string;
  onKeyDown?: (e: React.KeyboardEvent<HTMLDivElement>) => void;
  onPaste?: (e: React.ClipboardEvent<HTMLDivElement>) => void;
}) {
  const people = usePeople();
  const index = useMemo(() => indexPeople(people), [people]);
  const ref = useRef<HTMLDivElement>(null);
  const emitted = useRef<string | null>(null);
  const [suggest, setSuggest] = useState<Suggest | null>(null);
  const [active, setActive] = useState(0);

  const find = (uid?: string, name?: string) => resolveTag(index, uid, name);

  // Show `value` when it changes from outside (first render, cleared after sending, people loaded).
  useEffect(() => {
    const root = ref.current;
    if (!root || value === emitted.current) return;
    render(root, value, find);
    // Until people are loaded, tags can't be drawn yet: draw again when they arrive.
    emitted.current = people.length && serialize(root) === value ? value : null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, index]);

  useEffect(() => {
    if (!autoFocus || !ref.current) return;
    ref.current.focus();
    caretAtEnd(ref.current);
  }, [autoFocus]);

  const options = useMemo(
    () =>
      suggest
        ? people.filter((p) => p.active && matchesQuery(p, suggest.query)).slice(0, MAX_SUGGESTIONS)
        : [],
    [people, suggest],
  );

  function emit() {
    const text = serialize(ref.current!);
    if (!text) ref.current!.replaceChildren(); // so the placeholder shows again
    emitted.current = text;
    onChange(text);
  }

  /** Blue names whose text was edited go back to plain "@text", keeping the caret in place. */
  function unchipEdited() {
    const sel = window.getSelection();
    ref.current!.querySelectorAll<HTMLSpanElement>("span[data-uid]").forEach((span) => {
      const text = span.textContent ?? "";
      if (text === span.dataset.name) return;
      let caret: number | null = null;
      if (sel?.anchorNode && span.contains(sel.anchorNode)) {
        const range = document.createRange();
        range.setStart(span, 0);
        range.setEnd(sel.anchorNode, sel.anchorOffset);
        caret = range.toString().length;
      }
      const plain = document.createTextNode(text ? "@" + text : "");
      span.replaceWith(plain);
      if (caret !== null) placeCaret(plain, Math.min(caret + 1, plain.length));
    });
  }

  /** After a space or punctuation, a real "@username" right before it becomes a blue name. */
  function chipTyped() {
    const sel = window.getSelection();
    const node = sel?.anchorNode;
    if (!sel?.isCollapsed || !node || node.nodeType !== Node.TEXT_NODE) return;
    const before = (node.textContent ?? "").slice(0, sel.anchorOffset);
    const typed = before.slice(-1);
    if (!typed || /[\w.-]/.test(typed)) return;
    const m = before.slice(0, -1).match(TYPED_TAG_RE);
    const user = m && find(undefined, m[1]);
    if (!m || !user || m[1].toLowerCase() !== user.username.toLowerCase()) return;
    const start = before.length - 1 - m[1].length - 1;
    const text = node as Text;
    const rest = text.splitText(start);
    const after = rest.splitText(m[1].length + 1);
    rest.replaceWith(chip(user));
    placeCaret(after, 1);
  }

  function updateSuggest() {
    const sel = window.getSelection();
    const node = sel?.anchorNode;
    if (!sel?.isCollapsed || !node || node.nodeType !== Node.TEXT_NODE || !ref.current?.contains(node)) {
      setSuggest(null);
      return;
    }
    const before = (node.textContent ?? "").slice(0, sel.anchorOffset);
    const m = before.match(QUERY_RE);
    if (!m) {
      setSuggest(null);
      return;
    }
    // Line the list up with the "@" itself, not with the caret.
    const start = before.length - m[1].length - 1;
    const at = document.createRange();
    at.setStart(node, start);
    at.setEnd(node, start + 1);
    const rect = at.getBoundingClientRect();
    const above = rect.bottom + 280 > window.innerHeight && rect.top > 280;
    if (suggest?.query !== m[1]) setActive(0);
    setSuggest({
      node: node as Text,
      start,
      query: m[1],
      top: above ? window.innerHeight - rect.top + 4 : rect.bottom + 4,
      left: Math.max(8, Math.min(rect.left, window.innerWidth - 264)),
      above,
    });
  }

  // The list is placed on the page, so it has to follow the "@" when something scrolls or resizes.
  const open = suggest !== null;
  useEffect(() => {
    if (!open) return;
    const follow = () => updateSuggest();
    window.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    return () => {
      window.removeEventListener("scroll", follow, true);
      window.removeEventListener("resize", follow);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function pick(user: Person) {
    if (!suggest) return;
    const sel = window.getSelection();
    const { node, start } = suggest;
    const end = sel?.anchorNode === node ? sel.anchorOffset : start + suggest.query.length + 1;
    const rest = node.splitText(start);
    const after = rest.splitText(end - start);
    const space = document.createTextNode(" ");
    rest.replaceWith(chip(user), space);
    if (!after.length) after.remove();
    placeCaret(space, 1);
    setSuggest(null);
    emit();
  }

  return (
    <div className="relative min-w-0 flex-1">
      <div
        ref={ref}
        id={id}
        role="textbox"
        aria-multiline
        aria-placeholder={placeholder}
        contentEditable="plaintext-only"
        suppressContentEditableWarning
        dir="auto"
        data-placeholder={placeholder}
        className={cn(
          "break-words whitespace-pre-wrap outline-none empty:before:pointer-events-none empty:before:text-muted-foreground empty:before:content-[attr(data-placeholder)]",
          className,
        )}
        onInput={(e) => {
          if ((e.nativeEvent as InputEvent).isComposing) return;
          unchipEdited();
          if ((e.nativeEvent as InputEvent).inputType === "insertText") chipTyped();
          updateSuggest();
          emit();
        }}
        onCompositionEnd={() => {
          unchipEdited();
          updateSuggest();
          emit();
        }}
        onKeyDown={(e) => {
          if (e.nativeEvent.isComposing) return;
          if (suggest && options.length) {
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              const step = e.key === "ArrowDown" ? 1 : -1;
              setActive((a) => (a + step + options.length) % options.length);
              return;
            }
            if (e.key === "Enter" || e.key === "Tab") {
              e.preventDefault();
              pick(options[Math.min(active, options.length - 1)]);
              return;
            }
          }
          if (suggest && e.key === "Escape") {
            e.preventDefault();
            setSuggest(null);
            return;
          }
          onKeyDown?.(e);
          if (e.key === "Enter" && !e.defaultPrevented) {
            e.preventDefault();
            document.execCommand("insertLineBreak");
          }
        }}
        onKeyUp={(e) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) updateSuggest();
        }}
        onClick={updateSuggest}
        onBlur={() => setTimeout(() => setSuggest(null), 150)}
        onPaste={(e) => {
          onPaste?.(e);
          if (e.defaultPrevented) return;
          e.preventDefault();
          const text = e.clipboardData.getData("text/plain");
          if (!text) return;
          document.execCommand("insertText", false, text);
          // Pasted tags of real users become blue names.
          if (new RegExp(TAG_RE.source).test(text)) {
            const root = ref.current!;
            render(root, serialize(root), find);
            caretAtEnd(root);
          }
          emit();
        }}
      />
      {suggest &&
        options.length > 0 &&
        // On the page itself: a parent with a blur or transform would move a `fixed` list away from the "@".
        createPortal(
        <ul
          role="listbox"
          className="fixed z-50 max-h-64 w-64 overflow-y-auto rounded-lg border bg-popover p-1 text-popover-foreground shadow-md"
          style={suggest.above ? { bottom: suggest.top, left: suggest.left } : { top: suggest.top, left: suggest.left }}
        >
          {options.map((p, i) => (
            <li
              key={p.id}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(p);
              }}
              onMouseEnter={() => setActive(i)}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                i === active && "bg-muted",
              )}
            >
              <Avatar user={p} size={22} />
              <span className="min-w-0 flex-1 truncate">{p.display_name}</span>
              <span className="truncate text-xs text-muted-foreground">@{p.username}</span>
            </li>
          ))}
        </ul>,
          document.body,
        )}
    </div>
  );
}
