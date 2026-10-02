import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const toast = useToast();
  return <button onClick={() => toast("Profile saved", { description: "All good" })}>go</button>;
}

describe("Toast", () => {
  it("shows a toast and auto-dismisses it", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("go"));
    expect(screen.getByText("Profile saved")).toBeInTheDocument();
    expect(screen.getByText("All good")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.queryByText("Profile saved")).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("is a harmless no-op outside the provider", () => {
    render(<Trigger />);
    fireEvent.click(screen.getByText("go"));
    expect(screen.queryByText("Profile saved")).not.toBeInTheDocument();
  });
});
