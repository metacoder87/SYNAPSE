/** P8.2 (pulled into P4): component rendering + theme class checks (PRD §8). */

import { render, screen } from "@testing-library/react";
import JobCard from "@/components/JobCard";
import { Job } from "@/lib/api";

const baseJob: Job = {
  id: "11111111-1111-1111-1111-111111111111",
  source_provider: "usajobs",
  title: "Corporate AI Architect",
  company: "Defense Digital Service",
  department: null,
  location_string: "Anywhere in the U.S.",
  is_remote: true,
  job_url: "https://example.com/job",
  apply_url: null,
  salary_min: 150000,
  salary_max: 204000,
  salary_interval: "PA",
  security_clearance: "Top Secret",
  alignment_score: 0.5646,
  description_markdown: "# Role",
  posted_at: null,
  closing_date: "2026-08-15T23:59:59Z",
  system_status: "active",
};

test("renders title, company, and score", () => {
  render(<JobCard job={baseJob} />);
  expect(screen.getByText("Corporate AI Architect")).toBeInTheDocument();
  expect(screen.getByText("Defense Digital Service")).toBeInTheDocument();
  expect(screen.getByText("0.565")).toBeInTheDocument();
});

test("high score gets cyan glow theme classes", () => {
  render(<JobCard job={baseJob} />);
  const badge = screen.getByTestId("score-badge");
  expect(badge.className).toContain("text-cyber-cyan");
  expect(badge.className).toContain("shadow-glow-cyan");
});

test("renders clearance and remote badges", () => {
  render(<JobCard job={baseJob} />);
  expect(screen.getByText(/Top Secret/)).toBeInTheDocument();
  expect(screen.getByText("REMOTE")).toBeInTheDocument();
});

test("null score renders N/A without glow", () => {
  render(<JobCard job={{ ...baseJob, alignment_score: null }} />);
  const badge = screen.getByTestId("score-badge");
  expect(badge).toHaveTextContent("N/A");
  expect(badge.className).not.toContain("shadow-glow-cyan");
});

test("salary renders as compact range", () => {
  render(<JobCard job={baseJob} />);
  expect(screen.getByText("$150k–$204k/yr")).toBeInTheDocument();
});
