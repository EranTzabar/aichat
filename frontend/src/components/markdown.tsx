import type { Root } from "mdast";
import { findAndReplace } from "mdast-util-find-and-replace";
import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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

/** Scroll to a message of the current work and put its id in the URL, so the link can be shared. */
export function goToMessage(id: number | string) {
  const el = document.getElementById(`m${id}`);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  history.replaceState(null, "", `#m${id}`);
  return true;
}

/** Safe markdown: react-markdown never renders raw HTML. `messageIds` turns `#id` of those messages into links. */
export function Markdown({ children, messageIds }: { children: string; messageIds?: Set<number> }) {
  const plugins = useMemo(
    () => (messageIds ? [remarkGfm, remarkMessageLinks(messageIds)] : [remarkGfm]),
    [messageIds],
  );
  return (
    <div className="markdown break-words">
      <ReactMarkdown
        remarkPlugins={plugins}
        components={{
          a: ({ href, children, node: _node, ...props }) => {
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
