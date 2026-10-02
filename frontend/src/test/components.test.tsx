import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LevelBadge, NotAvailable } from "../components/ui";
import { FilePath } from "../components/FilePath";
import { AuthProvider } from "../lib/auth";
import { Signup } from "../pages/Auth";

function wrap(node: ReactNode) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AuthProvider>{node}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("display components", () => {
  it("shows Not available with the backend's reason", () => {
    render(<NotAvailable reason="ML risk analysis skipped: one class." />);
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.getByText("ML risk analysis skipped: one class.")).toBeInTheDocument();
  });

  it("renders engine levels in sentence case", () => {
    render(<LevelBadge level="CRITICAL" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("splits a file path into directory and name", () => {
    render(<FilePath path="src/core/payment.py" />);
    expect(screen.getByText("src/core/")).toBeInTheDocument();
    expect(screen.getByText("payment.py")).toBeInTheDocument();
  });
});

describe("Signup form", () => {
  it("validates before calling the API", () => {
    wrap(<Signup />);
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Enter your name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Use at least 8 characters.")).toBeInTheDocument();
  });

  it("checks that passwords match", () => {
    wrap(<Signup />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Ada" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ada@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "analytical1" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "analytical2" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
  });
});
