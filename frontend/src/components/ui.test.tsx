import { render, screen } from "@testing-library/react";
import { Folder } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { Button, EmptyState, Field, PageHeader, SectionLabel, StatCard } from "./ui";

describe("PageHeader", () => {
  it("renders the title and optional subtitle", () => {
    render(<PageHeader title="Opportunities" subtitle="Everything you've discovered" />);
    expect(screen.getByRole("heading", { level: 1, name: "Opportunities" })).toBeInTheDocument();
    expect(screen.getByText("Everything you've discovered")).toBeInTheDocument();
  });

  it("omits the subtitle paragraph when none is given", () => {
    render(<PageHeader title="Opportunities" />);
    expect(screen.queryByText(/Everything/)).not.toBeInTheDocument();
  });
});

describe("SectionLabel", () => {
  it("renders its children", () => {
    render(<SectionLabel>Evidence</SectionLabel>);
    expect(screen.getByText("Evidence")).toBeInTheDocument();
  });
});

describe("Field", () => {
  it("renders the label, children, and optional hint", () => {
    render(
      <Field label="Password" hint="At least 8 characters">
        <input />
      </Field>
    );
    expect(screen.getByText("Password")).toBeInTheDocument();
    expect(screen.getByText("At least 8 characters")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});

describe("Button", () => {
  it("fires onClick and respects the disabled state", () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} disabled>
        Submit
      </Button>
    );
    const button = screen.getByRole("button", { name: "Submit" });
    expect(button).toBeDisabled();
  });
});

describe("StatCard", () => {
  it("renders the value and label", () => {
    render(<StatCard icon={Folder} value={5} label="Urgent deadlines" tone="danger" />);
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Urgent deadlines")).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders title, description, and action", () => {
    render(
      <EmptyState
        icon={Folder}
        title="No applications yet"
        description="Ingest an opportunity to get started."
        action={<button>Ingest</button>}
      />
    );
    expect(screen.getByText("No applications yet")).toBeInTheDocument();
    expect(screen.getByText("Ingest an opportunity to get started.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ingest" })).toBeInTheDocument();
  });
});
