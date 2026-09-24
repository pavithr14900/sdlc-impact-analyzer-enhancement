import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Keep the document's source appendix available without interrupting its explanation. */
export default function DocumentProse({ content }: { content: string }) {
  const sections = content.split(/(?=^##[ \t]+Source Evidence[ \t]*\r?$)/m);
  return <div className="li-markdown li-document-prose">
    {sections.map((section, index) => {
      if (!/^##[ \t]+Source Evidence[ \t]*\r?\n/.test(section)) {
        return <ReactMarkdown key={index} remarkPlugins={[remarkGfm]}>{section}</ReactMarkdown>;
      }
      const body = section.replace(/^##[ \t]+Source Evidence[ \t]*\r?\n/, "");
      const nextHeading = body.search(/^#{1,2}[ \t]+/m);
      const evidence = nextHeading < 0 ? body : body.slice(0, nextHeading);
      const remainder = nextHeading < 0 ? "" : body.slice(nextHeading);
      return <div key={index}>
        <details className="li-evidence li-document-sources">
          <summary>Source evidence references</summary>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{evidence}</ReactMarkdown>
        </details>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{remainder}</ReactMarkdown>
      </div>;
    })}
  </div>;
}
