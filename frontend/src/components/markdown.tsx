import type { PhrasingContent, Root } from "mdast";
import { findAndReplace } from "mdast-util-find-and-replace";
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Mention } from "@/components/mention";
import { indexPeople, type PeopleIndex, splitTags, TAG_RE, usePeople } from "@/lib/people";
import type { UserRef } from "@/lib/types";

const MESSAGE_REF = /(?<![\w&#])#(\d+)\b/g;

/** Turns `#123` into a link to message 123, only for ids in `ids` (code and existing links are left alone). */
function remarkMessageLinks(ids: Set<number>) {
  return () => (tree: Root) => {
    findAndReplace(
      tree,
      [
        [
          MESSAGE_REF,
          (value: string, id: string) =>
            ids.has(Number(id)) ? { type: "link", url: `#m${id}`, children: [{ type: "text", value }] } : false,
        ],
      ],
      { ignore: ["link", "linkReference"] },
    );
  };
}

/** Turns tags of known users (`<@7>`, `@username`) into `#u7` links, drawn as blue names. */
function remarkMentions(index: PeopleIndex) {
  return () => (tree: Root) => {
    findAndReplace(
      tree,
      [
        [
          TAG_RE,
          (value: string) => {
            const parts = splitTags(value, index);
            if (parts.length === 1 && typeof parts[0] === "string") return false;
            return parts.map(
              (p): PhrasingContent =>
                typeof p === "string"
                  ? { type: "text", value: p }
                  : { type: "link", url: `#u${p.user.id}`, children: [{ type: "text", value: p.raw }] },
            );
          },
        ],
      ],
      { ignore: ["link", "linkReference"] },
    );
  };
}

/** Scroll to a message of the current chat and put its id in the URL, so the link can be shared. */
export function goToMessage(id: number | string) {
  const el = document.getElementById(`m${id}`);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  history.replaceState(null, "", `#m${id}`);
  return true;
}

/**
 * Safe markdown: react-markdown never renders raw HTML. `messageIds` turns `#id` of those messages into links.
 * Tags of users show as their names in blue; `mentions` (from the API) adds users to the known ones.
 */
export function Markdown({
  children,
  messageIds,
  mentions,
}: {
  children: string;
  messageIds?: Set<number>;
  mentions?: UserRef[];
}) {
  const people = usePeople();
  const index = useMemo(() => indexPeople(people, mentions), [people, mentions]);
  const plugins = useMemo(
    () => [remarkGfm, remarkMentions(index), ...(messageIds ? [remarkMessageLinks(messageIds)] : [])],
    [messageIds, index],
  );
  return (
    <div className="markdown break-words">
      <ReactMarkdown
        remarkPlugins={plugins}
        components={{
          a: ({ href, children, node: _node, ...props }) => {
            const tagged = href?.match(/^#u(\d+)$/);
            const user = tagged && index.byId.get(Number(tagged[1]));
            if (user) return <Mention user={user} />;
            const ref = href?.match(/^#m(\d+)$/);
            if (ref) {
              return (
                <a
                  href={href}
                  title={`Go to message #${ref[1]}`}
                  className="font-medium text-primary hover:underline"
                  onClick={(e) => {
                    if (goToMessage(ref[1])) e.preventDefault();
                  }}
                >
                  {children}
                </a>
              );
            }
            return (
              <a href={href} {...props} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
