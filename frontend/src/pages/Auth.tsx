import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { Logo } from "../components/Logo";
import { Button, Callout, cx, Field, Input } from "../components/ui";
import { useAuth } from "../lib/auth";
import { ApiError } from "../services/api";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function AuthShell({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center bg-canvas px-4 py-12">
      <Link to="/" className="mb-8" aria-label="CodePulse AI home">
        <Logo />
      </Link>
      <div className="panel w-full max-w-[400px] p-6 sm:p-7">
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-sm text-muted">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </div>
      <p className="mt-5 text-sm text-muted">{footer}</p>
    </div>
  );
}

function PasswordInput({
  id,
  value,
  onChange,
  invalid,
  autoComplete,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  autoComplete: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        invalid={invalid}
        autoComplete={autoComplete}
        className="pr-10"
      />
      <button
        type="button"
        onClick={() => setVisible((shown) => !shown)}
        className="absolute right-1.5 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-faint hover:text-ink"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

export function passwordStrength(password: string): { score: number; label: string } {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  const capped = Math.min(4, score);
  return { score: capped, label: ["Too weak", "Weak", "Fair", "Good", "Strong"][capped] };
}

function StrengthMeter({ password }: { password: string }) {
  if (!password) return <span>At least 8 characters, with a letter and a number.</span>;
  const { score, label } = passwordStrength(password);
  const color = score <= 1 ? "bg-critical" : score === 2 ? "bg-medium" : "bg-low";
  return (
    <div className="flex items-center gap-2" aria-live="polite">
      <div className="flex flex-1 gap-1" aria-hidden>
        {[0, 1, 2, 3].map((index) => (
          <span key={index} className={cx("h-1 flex-1 rounded-full", index < score ? color : "bg-raised")} />
        ))}
      </div>
      <span className="w-16 text-right">{label}</span>
    </div>
  );
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!EMAIL.test(email.trim())) next.email = "Enter a valid email address.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length) return;
    setSubmitting(true);
    try {
      await login(email.trim(), password, remember);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from.startsWith("/app") ? from : "/app", { replace: true });
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : "Sign in failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title="Sign in"
      subtitle="Welcome back to CodePulse AI."
      footer={
        <>
          New to CodePulse?{" "}
          <Link to="/signup" className="font-medium text-accent hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        {formError && <Callout tone="error">{formError}</Callout>}
        <Field label="Email" htmlFor="email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            invalid={Boolean(errors.email)}
            autoFocus
          />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password}>
          <PasswordInput
            id="password"
            value={password}
            onChange={setPassword}
            invalid={Boolean(errors.password)}
            autoComplete="current-password"
          />
        </Field>
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
            className="h-4 w-4 rounded border-line accent-[rgb(var(--accent))]"
          />
          Keep me signed in on this device
        </label>
        <Button type="submit" variant="primary" loading={submitting} className="w-full">
          Sign in
        </Button>
      </form>
    </AuthShell>
  );
}

export function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [values, setValues] = useState({ name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const set = (key: keyof typeof values) => (value: string) => setValues((current) => ({ ...current, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!values.name.trim()) next.name = "Enter your name.";
    if (!EMAIL.test(values.email.trim())) next.email = "Enter a valid email address.";
    if (values.password.length < 8) next.password = "Use at least 8 characters.";
    else if (!/[A-Za-z]/.test(values.password) || !/\d/.test(values.password))
      next.password = "Include at least one letter and one number.";
    if (values.confirm !== values.password) next.confirm = "Passwords do not match.";
    setErrors(next);
    setFormError(null);
    if (Object.keys(next).length) return;
    setSubmitting(true);
    try {
      await signup(values.name.trim(), values.email.trim(), values.password);
      navigate("/app", { replace: true });
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fieldErrors).length) setErrors(error.fieldErrors);
      else setFormError(error instanceof ApiError ? error.message : "Sign up failed. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      title="Create your account"
      subtitle="Analyze repositories and keep your results in one place."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-accent hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        {formError && <Callout tone="error">{formError}</Callout>}
        <Field label="Name" htmlFor="name" error={errors.name}>
          <Input
            id="name"
            autoComplete="name"
            value={values.name}
            onChange={(event) => set("name")(event.target.value)}
            invalid={Boolean(errors.name)}
            autoFocus
          />
        </Field>
        <Field label="Email" htmlFor="email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={values.email}
            onChange={(event) => set("email")(event.target.value)}
            invalid={Boolean(errors.email)}
          />
        </Field>
        <Field label="Password" htmlFor="password" error={errors.password} hint={<StrengthMeter password={values.password} />}>
          <PasswordInput
            id="password"
            value={values.password}
            onChange={set("password")}
            invalid={Boolean(errors.password)}
            autoComplete="new-password"
          />
        </Field>
        <Field label="Confirm password" htmlFor="confirm" error={errors.confirm}>
          <PasswordInput
            id="confirm"
            value={values.confirm}
            onChange={set("confirm")}
            invalid={Boolean(errors.confirm)}
            autoComplete="new-password"
          />
        </Field>
        <Button type="submit" variant="primary" loading={submitting} className="w-full">
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
