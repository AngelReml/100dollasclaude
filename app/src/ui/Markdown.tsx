import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** An AI's answer: markdown only, never raw HTML; links open outside, images are not loaded. */
export function Markdown({ text }: { text: string }) {
  return (
    <div className="prose-answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          img: ({ alt, src }) => (
            <a href={typeof src === "string" ? src : undefined} target="_blank" rel="noopener noreferrer">
              [imagen: {alt || "sin descripción"}]
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
