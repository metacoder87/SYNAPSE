/** P8.2 — react-markdown injection stress test (PRD §8): heavy tables and
 *  link formatting must render inside the themed components without breaking. */

import { render, screen } from "@testing-library/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { markdownComponents } from "@/lib/markdown";

function renderMd(md: string) {
  return render(
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
      {md}
    </ReactMarkdown>
  );
}

const HEAVY_TABLE = `
# Dossier

| Product | Stack | ${"Very Long Header ".repeat(8)} |
|---------|-------|------|
${Array.from({ length: 25 }, (_, i) => `| Item ${i} | FastAPI | ${"cell ".repeat(30)} |`).join("\n")}
`;

test("25-row wide table renders in a scroll container", () => {
  const { container } = renderMd(HEAVY_TABLE);
  const table = container.querySelector("table");
  expect(table).toBeInTheDocument();
  expect(container.querySelectorAll("tr").length).toBeGreaterThanOrEqual(26);
  // wrapped in the overflow guard so wide tables can't break the grid
  expect(table!.parentElement!.className).toContain("overflow-x-auto");
});

test("links get safe attributes and theme class", () => {
  renderMd("[apply here](https://example.com/jobs/1?a=b&c=d)");
  const link = screen.getByRole("link", { name: "apply here" });
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(link.className).toContain("text-cyber-cyan");
});

test("raw HTML in markdown is NOT rendered as elements (XSS guard)", () => {
  const { container } = renderMd('before <img src=x onerror="alert(1)"> after');
  expect(container.querySelector("img")).toBeNull();
});

test("100 mixed blocks render without throwing", () => {
  const big = Array.from(
    { length: 100 },
    (_, i) => `## Section ${i}\n\n- point one with [link](https://x.dev/${i})\n- *emphasis*\n`
  ).join("\n");
  const { container } = renderMd(big);
  expect(container.querySelectorAll("h2").length).toBe(100);
  expect(container.querySelectorAll("a").length).toBe(100);
});
