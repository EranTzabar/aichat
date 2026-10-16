import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Safe markdown: react-markdown never renders raw HTML. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="markdown break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
