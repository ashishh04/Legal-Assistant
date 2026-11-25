import { Fragment, type ReactNode } from "react";

/** Citation markers are embedded in the text as \u0001<n>\u0002 before parsing. */
export const citeMark = (n: number) => `\u0001${n}\u0002`;

type Block =
  | { type: "p"; lines: string[] }
  | { type: "ul" | "ol"; items: string[] }
  | { type: "h"; text: string }
  | { type: "table"; head: string[]; rows: string[][] };

const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|[\s:|-]+\|\s*$/;

function parseBlocks(text: string): Block[] {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: { type: "ul" | "ol"; items: string[] } | null = null;
  const flushPara = () => { if (para.length) { blocks.push({ type: "p", lines: para }); para = []; } };
  const flushList = () => { if (list) { blocks.push(list); list = null; } };
  const cells = (line: string) => line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_RULE.test(lines[i + 1])) {
      flushPara(); flushList();
      const head = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && TABLE_ROW.test(lines[i])) rows.push(cells(lines[i++]));
      i--;
      blocks.push({ type: "table", head, rows });
      continue;
    }
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const heading = line.match(/^\s*#{1,6}\s+(.*)$/);
    if (bullet || numbered) {
      flushPara();
      const type = bullet ? "ul" : "ol";
      if (!list || list.type !== type) { flushList(); list = { type, items: [] }; }
      list.items.push((bullet ?? numbered)![1]);
    } else if (heading) {
      flushPara(); flushList();
      blocks.push({ type: "h", text: heading[1] });
    } else if (!line.trim()) {
      flushPara(); flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara(); flushList();
  return blocks;
}

function inline(text: string, renderCite: (n: number) => ReactNode, keyBase: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\u0001\d+\u0002)/g);
  return parts.map((part, i) => {
    const key = `${keyBase}-${i}`;
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={key} className="font-semibold">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={key} className="rounded bg-surface-3 px-1 py-0.5 text-[0.85em]">{part.slice(1, -1)}</code>;
    const cite = part.match(/^\u0001(\d+)\u0002$/);
    if (cite) return <Fragment key={key}>{renderCite(Number(cite[1]))}</Fragment>;
    return <Fragment key={key}>{part}</Fragment>;
  });
}

export function Markdown({ text, renderCite }: { text: string; renderCite: (n: number) => ReactNode }) {
  const blocks = parseBlocks(text);
  return (
    <div className="space-y-3 text-[14.5px] leading-[1.65] text-ink">
      {blocks.map((b, i) => {
        const k = `b${i}`;
        switch (b.type) {
          case "p":
            return (
              <p key={k} dir="auto">
                {b.lines.map((l, j) => (
                  <Fragment key={j}>{j > 0 && <br />}{inline(l, renderCite, `${k}-${j}`)}</Fragment>
                ))}
              </p>
            );
          case "h":
            return <p key={k} dir="auto" className="font-semibold">{inline(b.text, renderCite, k)}</p>;
          case "ul":
          case "ol": {
            const List = b.type;
            return (
              <List key={k} className={`${b.type === "ul" ? "list-disc" : "list-decimal"} space-y-1 ps-5 marker:text-muted`}>
                {b.items.map((it, j) => <li key={j} dir="auto">{inline(it, renderCite, `${k}-${j}`)}</li>)}
              </List>
            );
          }
          case "table":
            return (
              <div key={k} className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-[13.5px]" dir="auto">
                  <thead className="bg-surface-2 text-left text-[12.5px] text-muted">
                    <tr>{b.head.map((h, j) => <th key={j} className="px-3 py-2 font-medium">{inline(h, renderCite, `${k}-h${j}`)}</th>)}</tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, j) => (
                      <tr key={j} className="border-t border-line">
                        {r.map((c, m) => <td key={m} className="px-3 py-2 align-top">{inline(c, renderCite, `${k}-${j}-${m}`)}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}
