'use client';

/* oxlint-disable typescript/no-deprecated, next/no-img-element, jsx-a11y/prefer-tag-over-role -- React form handlers use FormEvent; authenticated SVG previews are intentionally plain images; the graphical label canvas uses ARIA roles because native select/option/range controls cannot represent movable and resizable canvas objects. */

import { FormEvent, KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent, useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Archive,
  Boxes,
  ChevronRight,
  CircleGauge,
  CloudDownload,
  Database,
  Download,
  Ellipsis,
  Eye,
  EyeOff,
  GripVertical,
  Inbox,
  LayoutGrid,
  Layers3,
  LogOut,
  Plus,
  Copy,
  Pencil,
  Printer as PrinterIcon,
  RefreshCw,
  RotateCcw,
  Save,
  Scale,
  Search,
  Settings,
  SlidersHorizontal,
  TableProperties,
  UserPlus,
  Users,
  X,
} from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  NativeSelect,
  NativeSelectOption,
} from '@/components/ui/native-select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';

type NavKey = 'overview' | 'spools' | 'printers' | 'jobs' | 'settings';
type User = {
  id: string;
  email: string;
  displayName: string;
  role: string;
  preferredUnit: 'grams' | 'meters' | 'both';
  mustChangePassword: boolean;
  active: boolean;
  createdAt: string;
};
type Spool = {
  id: string;
  code: string;
  brand: string;
  materialName: string;
  materialType: string;
  colorName: string;
  colorHex: string;
  location: string;
  lotNumber: string;
  serialNumber: string;
  diameterMm: number;
  density: number;
  tareWeightG: number;
  lowStockWeightG: number;
  purchasePrice: number | null;
  currency: string;
  catalogSnapshot: Record<string, unknown>;
  openPrintTag: {
    brandUuid: string | null;
    materialUuid: string | null;
    packageUuid: string | null;
    containerUuid: string | null;
  };
  initialWeightG: number;
  remainingWeightG: number;
  reservedWeightG: number;
  availableWeightG: number;
  initialLengthM: number;
  remainingLengthM: number;
  reservedLengthM: number;
  availableLengthM: number;
  remainingPercent: number;
  lowStock: boolean;
  archived: boolean;
  discrepancy: boolean;
  loadedOn?: { printerId: string; printer: string; printerCode: string; toolId: string; tool: string } | null;
  productKey: string;
  lastWeighedAt: string | null;
};
type SpoolFilters = {
  brand: string;
  material: string;
  color: string;
  location: string;
  loadState: string;
  stockState: string;
  printer: string;
  similarColor: string;
  deltaE: string;
};
type SpoolColumn = 'code' | 'color' | 'brand' | 'filament' | 'material' | 'remaining' | 'reserved' | 'available' | 'location' | 'loadout' | 'status';
const SPOOL_COLUMNS: Array<{ key: SpoolColumn; label: string }> = [
  { key: 'code', label: 'Code' }, { key: 'color', label: 'Color' },
  { key: 'brand', label: 'Brand' }, { key: 'filament', label: 'Filament' },
  { key: 'material', label: 'Material' }, { key: 'remaining', label: 'Remaining' },
  { key: 'reserved', label: 'Reserved' }, { key: 'available', label: 'Available' },
  { key: 'location', label: 'Location' }, { key: 'loadout', label: 'Loadout' },
  { key: 'status', label: 'Status' },
];
const EMPTY_SPOOL_FILTERS: SpoolFilters = {
  brand: '',
  material: '',
  color: '',
  location: '',
  loadState: '',
  stockState: '',
  printer: '',
  similarColor: '',
  deltaE: '12',
};
type Tool = {
  id: string;
  index: number;
  label: string;
  nozzleDiameterMm: number | null;
  loadedSpool: null | {
    id: string;
    code: string;
    brand: string;
    material: string;
    colorHex: string;
    remainingWeightG: number;
    remainingLengthM: number;
    materialType: string;
  };
};
type Printer = {
  id: string;
  code: string;
  name: string;
  manufacturer: string;
  model: string;
  location: string;
  slicerProfile: string;
  notes: string;
  archived: boolean;
  tools: Tool[];
};
type Usage = {
  id: string;
  toolIndex: number;
  toolLabel: string;
  materialType: string;
  colorHex: string;
  estimatedLengthM: number;
  estimatedWeightG: number;
  actualLengthM: number | null;
  actualWeightG: number | null;
  suggestedSpoolId: string | null;
  mappedSpoolId: string | null;
};
type Job = {
  id: string;
  code: string;
  displayName: string;
  filename: string;
  status: string;
  estimatedSeconds: number | null;
  createdAt: string;
  warnings: string[];
  slicerProfile: string;
  routingMode: string;
  printer: { id: string; code: string; name: string };
  usages: Usage[];
};
type UsageAnalytics = {
  range: { from: string; to: string; days: number; timezone: string };
  totals: { weightG: number; lengthM: number };
  points: Array<{ date: string; weightG: number; lengthM: number }>;
};
type Dashboard = {
  summary: {
    remainingWeightG: number;
    remainingLengthM: number;
    reservedWeightG: number;
    reservedLengthM: number;
    mappedReservedWeightG: number;
    mappedReservedLengthM: number;
    unassignedReservedWeightG: number;
    unassignedReservedLengthM: number;
    availableWeightG: number;
    availableLengthM: number;
    activeSpools: number;
    lowStockSpools: number;
    loadedSpools: number;
    openJobs: number;
    negativeSpools: number;
  };
  spools: Spool[];
  printers: Printer[];
  jobs: Job[];
  attention: OperationalStatus;
  reorder: ReorderPayload;
};
type OperationalStatus = {
  catalog: { ready: boolean; updatedAt: string | null; stale: boolean; failed: boolean };
  backup: { ready: boolean; updatedAt: string | null; stale: boolean };
  oldestOpenJobAt: string | null;
  staleJobs: number;
  unknownProfiles: number;
  unweighedSpools: number;
};
type ReorderGroup = {
  productKey: string; brand: string; materialName: string; materialType: string;
  colorName: string; colorHex: string; diameterMm: number; spoolCount: number;
  remainingWeightG: number; reservedWeightG: number; availableWeightG: number;
  remainingLengthM: number; reservedLengthM: number; availableLengthM: number;
  thresholdG: number; shortageG: number; ignored: boolean; needsOrdering: boolean;
};
type ReorderPayload = { defaultThresholdG: number; groups: ReorderGroup[] };
type ActivityItem = { id: string; action: string; details: Record<string, unknown>; createdAt: string };
type LabelElement = {
  id: string; type: string; x: number; y: number; width: number; height: number;
  font_size: number; visible: boolean; text: string; bold: boolean;
};
type LabelTemplate = {
  id: string; name: string; widthMm: number; heightMm: number; layout: LabelElement[];
  builtin: boolean; isDefault: boolean; archived: boolean; createdAt: string; updatedAt: string;
};
type CatalogItem = {
  id: string;
  brand: string;
  materialName: string;
  materialType: string;
  colorName: string;
  colorHex: string;
  diameterMm: number;
  density: number;
  nominalWeightG: number | null;
  nominalLengthM: number | null;
  tareWeightG: number | null;
  packageName: string;
  containerName: string;
  gtin: string;
  productUrl: string;
  photoUrl: string | null;
  tags: string[];
  properties: Record<string, unknown>;
  opt: Record<string, string | null>;
  raw: Record<string, unknown>;
};

function csrfToken() {
  return (
    document.cookie
      .split('; ')
      .find((row) => row.startsWith('filaflow_csrf='))
      ?.split('=')[1] ?? ''
  );
}
async function api<T = Record<string, unknown>>(
  url: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  if (init.method && !['GET', 'HEAD'].includes(init.method))
    headers.set('X-CSRF-Token', csrfToken());
  const response = await fetch(url, {
    credentials: 'include',
    ...init,
    headers,
  });
  if (!response.ok) {
    const payload = (await response
      .json()
      .catch(() => ({ detail: `HTTP ${response.status}` }))) as {
      detail?: string;
    };
    throw new Error(payload.detail || 'Something went wrong');
  }
  return response.json() as Promise<T>;
}
const formatWeight = (grams: number) =>
  grams >= 1000
    ? `${(grams / 1000).toLocaleString('en-US', { maximumFractionDigits: 2 })} kg`
    : `${grams.toLocaleString('en-US', { maximumFractionDigits: 1 })} g`;
const formatLength = (meters: number) =>
  meters >= 1000
    ? `${(meters / 1000).toLocaleString('en-US', { maximumFractionDigits: 2 })} km`
    : `${meters.toLocaleString('en-US', { maximumFractionDigits: 1 })} m`;
const formatInventory = (weightG: number, lengthM: number, preference: User['preferredUnit'] = 'both') =>
  preference === 'grams'
    ? formatWeight(weightG)
    : preference === 'meters'
      ? formatLength(lengthM)
      : `${formatWeight(weightG)} · ${formatLength(lengthM)}`;
const formText = (form: FormData, name: string) => {
  const value = form.get(name);
  return typeof value === 'string' ? value : '';
};

export function FilaFlowApp() {
  const [user, setUser] = useState<User | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [spools, setSpools] = useState<Spool[]>([]);
  const [printers, setPrinters] = useState<Printer[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<NavKey>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [spoolDialog, setSpoolDialog] = useState(false);
  const [spoolTemplate, setSpoolTemplate] = useState<Spool | null>(null);
  const [printerDialog, setPrinterDialog] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [pollFailures, setPollFailures] = useState(0);
  const [newJobCount, setNewJobCount] = useState(0);
  const [pollRetry, setPollRetry] = useState(0);
  const revisionRef = useRef('');
  const jobIdsRef = useRef<Set<string> | null>(null);

  const refresh = useCallback(async () => {
    const [dash, spoolRows, printerRows, jobRows] = await Promise.all([
      api<Dashboard>('/api/dashboard'),
      api<Spool[]>('/api/spools'),
      api<Printer[]>('/api/printers'),
      api<Job[]>('/api/jobs'),
    ]);
    setDashboard(dash);
    setSpools(spoolRows);
    setPrinters(printerRows);
    setJobs(jobRows);
    setSelectedJob((current) => current ? jobRows.find((row) => row.id === current.id) ?? current : null);
    const nextOpen = new Set(jobRows.filter((job) => ['NEW', 'MAPPED', 'NEEDS_REVIEW'].includes(job.status)).map((job) => job.id));
    if (jobIdsRef.current) {
      const additions = [...nextOpen].filter((id) => !jobIdsRef.current?.has(id)).length;
      if (additions) setNewJobCount((count) => count + additions);
    }
    jobIdsRef.current = nextOpen;
  }, []);
  useEffect(() => {
    api<User>('/api/auth/me')
      .then((me) => {
        setUser(me);
        return me.mustChangePassword ? undefined : refresh();
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, [refresh]);
  useEffect(() => {
    if (!user || user.mustChangePassword) return;
    let stopped = false;
    async function checkRevision() {
      if (document.visibilityState === 'hidden') return;
      try {
        const headers = new Headers();
        if (revisionRef.current) headers.set('If-None-Match', `"${revisionRef.current}"`);
        const response = await fetch('/api/state/revision', { credentials: 'include', headers });
        if (response.status === 401) { location.reload(); return; }
        if (response.status === 304) { if (!stopped) setPollFailures(0); return; }
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const value = (await response.json()) as { revision: string };
        if (revisionRef.current && value.revision !== revisionRef.current) await refresh();
        revisionRef.current = value.revision;
        if (!stopped) setPollFailures(0);
      } catch {
        if (!stopped) setPollFailures((count) => count + 1);
      }
    }
    void checkRevision();
    const timer = window.setInterval(checkRevision, 5000);
    const visible = () => { if (document.visibilityState === 'visible') void checkRevision(); };
    window.addEventListener('focus', visible);
    document.addEventListener('visibilitychange', visible);
    return () => {
      stopped = true;
      window.clearInterval(timer);
      window.removeEventListener('focus', visible);
      document.removeEventListener('visibilitychange', visible);
    };
  }, [refresh, user, pollRetry]);
  useEffect(() => {
    document.title = newJobCount > 0 ? `(+${newJobCount}) FilaFlow` : 'FilaFlow';
    return () => { document.title = 'FilaFlow'; };
  }, [newJobCount]);
  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    const data = new FormData(event.currentTarget);
    try {
      const result = await api<{ user: User }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: data.get('email'),
          password: data.get('password'),
        }),
      });
      setUser(result.user);
      if (!result.user.mustChangePassword) await refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed');
    }
  }
  if (loading)
    return (
      <div className="grid min-h-screen place-items-center bg-background">
        <RefreshCw className="size-6 animate-spin text-primary" />
        <span className="sr-only">Loading</span>
      </div>
    );
  if (!user) return <LoginScreen onSubmit={login} error={error} />;
  if (user.mustChangePassword)
    return <RequiredPasswordChange user={user} onChanged={(updated) => { setUser(updated); void refresh(); }} onLogout={async () => { await api('/api/auth/logout', { method: 'POST' }); location.reload(); }} />;
  if (typeof window !== 'undefined' && window.location.pathname === '/labels/print')
    return <LabelPrintView spools={spools} />;
  if (typeof window !== 'undefined' && /^\/spools\/[0-9a-f-]+$/i.test(window.location.pathname))
    return <DirectSpoolView spoolId={window.location.pathname.split('/').at(-1) ?? ''} preference={user.preferredUnit} />;

  function navigate(key: NavKey) {
    setActive(key);
    if (key === 'jobs') setNewJobCount(0);
  }

  const openJobs = jobs.filter((job) =>
    ['NEW', 'MAPPED', 'NEEDS_REVIEW'].includes(job.status),
  );
  const nav: Array<[NavKey, string, typeof CircleGauge]> = [
    ['overview', 'Overview', CircleGauge],
    ['spools', 'Spools', Layers3],
    ['printers', 'Printers', PrinterIcon],
    ['jobs', 'Print inbox', Inbox],
    ['settings', 'Settings', Settings],
  ];
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="grid min-h-screen lg:grid-cols-[244px_1fr]">
        <aside className="hidden border-r border-sidebar-border bg-sidebar px-4 py-5 lg:flex lg:flex-col">
          <Brand />
          <nav className="space-y-1" aria-label="Main navigation">
            {nav.map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => navigate(key)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${active === key ? 'bg-primary text-primary-foreground shadow-sm' : 'text-sidebar-foreground hover:bg-sidebar-accent'}`}
              >
                <Icon className="size-4" />
                <span>{label}</span>
                {key === 'jobs' && openJobs.length > 0 && (
                  <span className="ml-auto rounded-full bg-orange-500 px-2 py-0.5 text-[10px] text-white">
                    {openJobs.length}
                  </span>
                )}
              </button>
            ))}
          </nav>
          <CatalogStatus />
        </aside>
        <section className="min-w-0 pb-20 lg:pb-0">
          <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/90 px-5 backdrop-blur md:px-8">
            <h1 className="text-lg font-bold tracking-tight">
              {nav.find(([key]) => key === active)?.[1]}
            </h1>
            <div className="flex items-center gap-2">
              {pollFailures >= 3 && (
                <Button size="sm" variant="outline" onClick={() => { setPollFailures(0); setPollRetry((value) => value + 1); }}>
                  <RefreshCw className="size-3.5" /> Updates paused · Retry
                </Button>
              )}
              {active === 'spools' && (
                <Button
                  className="rounded-xl"
                  onClick={() => { setSpoolTemplate(null); setSpoolDialog(true); }}
                >
                  <Plus className="size-4" /> Add spool
                </Button>
              )}
              {active === 'printers' && (
                <Button
                  className="rounded-xl"
                  onClick={() => setPrinterDialog(true)}
                >
                  <Plus className="size-4" /> Add printer
                </Button>
              )}
            </div>
          </header>
          <div className="mx-auto max-w-[1480px] p-5 md:p-8">
            {active === 'overview' && dashboard && (
              <Overview
                dashboard={dashboard}
                preference={user.preferredUnit}
                onNavigate={navigate}
                onJob={setSelectedJob}
                onAddSpool={() => { setSpoolTemplate(null); setSpoolDialog(true); }}
                onAddPrinter={() => setPrinterDialog(true)}
              />
            )}
            {active === 'spools' && (
              <SpoolsView
                spools={spools}
                preference={user.preferredUnit}
                isAdmin={user.role === 'admin'}
                onRefresh={refresh}
                onAdd={() => { setSpoolTemplate(null); setSpoolDialog(true); }}
                onDuplicate={(spool) => { setSpoolTemplate(spool); setSpoolDialog(true); }}
              />
            )}
            {active === 'printers' && (
              <PrintersView
                printers={printers}
                spools={spools}
                preference={user.preferredUnit}
                onRefresh={refresh}
              />
            )}
            {active === 'jobs' && (
              <JobsView jobs={jobs} onSelect={setSelectedJob} />
            )}
            {active === 'settings' && (
              <SettingsView
                user={user}
                printers={printers}
                spools={spools}
                onUserUpdated={setUser}
                onLogout={async () => {
                  await api('/api/auth/logout', { method: 'POST' });
                  location.reload();
                }}
              />
            )}
          </div>
        </section>
      </div>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t bg-background/95 px-2 py-2 backdrop-blur lg:hidden">
        {nav.map(([key, label, Icon]) => (
          <button
            key={key}
            onClick={() => navigate(key)}
            className={`flex min-w-12 flex-col items-center gap-1 rounded-lg px-2 py-1 text-[10px] ${active === key ? 'text-primary' : 'text-muted-foreground'}`}
          >
            <Icon className="size-4" />
            {label}
            {key === 'jobs' && openJobs.length > 0 && <span className="absolute ml-5 -mt-5 rounded-full bg-orange-500 px-1.5 text-[9px] text-white">{openJobs.length}</span>}
          </button>
        ))}
      </nav>
      <AddSpoolDialog
        open={spoolDialog}
        onOpenChange={(open) => { setSpoolDialog(open); if (!open) setSpoolTemplate(null); }}
        onCreated={refresh}
        template={spoolTemplate}
      />
      <AddPrinterDialog
        open={printerDialog}
        onOpenChange={setPrinterDialog}
        onCreated={refresh}
      />
      {selectedJob && (
        <JobDialog
          key={`${selectedJob.id}:${selectedJob.status}:${selectedJob.printer.id}:${selectedJob.warnings.join('|')}:${selectedJob.usages.map((usage) => `${usage.id}-${usage.mappedSpoolId ?? usage.suggestedSpoolId ?? ''}`).join('|')}`}
          job={selectedJob}
          spools={spools}
          printers={printers}
          open
          onOpenChange={(open) => !open && setSelectedJob(null)}
          onUpdated={async () => {
            setSelectedJob(null);
            await refresh();
          }}
        />
      )}
    </main>
  );
}

function LoginScreen({
  onSubmit,
  error,
}: {
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  error: string;
}) {
  return (
    <main className="grid min-h-screen place-items-center bg-[#14241f] p-6">
      <div className="w-full max-w-sm rounded-3xl bg-background p-7 shadow-2xl">
        <Brand />
        <h1 className="mt-8 text-2xl font-bold">Sign in</h1>
        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Field
            label="Email address"
            name="email"
            type="email"
            defaultValue="admin@filaflow.local"
            required
          />
          <Field label="Password" name="password" type="password" required />
          {error && (
            <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </p>
          )}
          <Button className="h-11 w-full rounded-xl" type="submit">
            Sign in
          </Button>
        </form>
      </div>
    </main>
  );
}

function RequiredPasswordChange({ user, onChanged, onLogout }: { user: User; onChanged: (user: User) => void; onLogout: () => void }) {
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next = formText(form, 'newPassword');
    setError('');
    if (next !== formText(form, 'confirmPassword')) { setError('New passwords do not match'); return; }
    try {
      const updated = await api<User>('/api/account/password', { method: 'PUT', body: JSON.stringify({ current_password: formText(form, 'currentPassword'), new_password: next }) });
      onChanged(updated);
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Password change failed'); }
  }
  return (
    <main className="grid min-h-screen place-items-center bg-[#14241f] p-6">
      <div className="w-full max-w-md rounded-3xl bg-background p-7 shadow-2xl">
        <Brand />
        <h1 className="text-2xl font-bold">Choose a new password</h1>
        <p className="mt-1 text-sm text-muted-foreground">Signed in as {user.email}</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <PasswordField label="Temporary password" name="currentPassword" autoComplete="current-password" required />
          <PasswordField label="New password" name="newPassword" minLength={12} autoComplete="new-password" required />
          <PasswordField label="Confirm new password" name="confirmPassword" minLength={12} autoComplete="new-password" required />
          {error && <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
          <Button className="w-full" type="submit">Change password</Button>
          <Button className="w-full" type="button" variant="ghost" onClick={onLogout}>Sign out</Button>
        </form>
      </div>
    </main>
  );
}
function Brand() {
  return (
    <div className="flex items-center gap-3 px-2 pb-7">
      <div className="grid size-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
        <Boxes className="size-5" />
      </div>
      <p className="text-sm font-bold tracking-tight">FilaFlow</p>
    </div>
  );
}
function CatalogStatus() {
  const [status, setStatus] = useState<{
    ready: boolean;
    count: number;
  } | null>(null);
  useEffect(() => {
    api<{ ready: boolean; count: number }>('/api/catalog/status')
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);
  return (
    <div className="mt-auto rounded-2xl border border-sidebar-border bg-background/70 p-3">
      <p className="text-xs font-semibold">OpenPrintTag</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        {status?.ready
          ? `${status.count.toLocaleString('en-US')} products available`
          : 'Catalog not synchronized'}
      </p>
      <div
        className={`mt-3 flex items-center gap-2 text-xs ${status?.ready ? 'text-emerald-600' : 'text-orange-600'}`}
      >
        <span
          className={`size-2 rounded-full ${status?.ready ? 'bg-emerald-500' : 'bg-orange-500'}`}
        />
        {status?.ready ? 'Snapshot active' : 'Not synchronized'}
      </div>
    </div>
  );
}

function Overview({
  dashboard,
  preference,
  onNavigate,
  onJob,
  onAddSpool,
  onAddPrinter,
}: {
  dashboard: Dashboard;
  preference: User['preferredUnit'];
  onNavigate: (key: NavKey) => void;
  onJob: (job: Job) => void;
  onAddSpool: () => void;
  onAddPrinter: () => void;
}) {
  const s = dashboard.summary;
  const metrics = [
    {
      label: 'Available',
      value: formatInventory(s.availableWeightG, s.availableLengthM, preference),
      note: `After ${s.openJobs} open jobs · ${s.activeSpools} active spools`,
      icon: CircleGauge,
    },
    {
      label: 'Reserved',
      value: formatInventory(s.reservedWeightG, s.reservedLengthM, preference),
      note: `${s.openJobs} jobs · ${formatInventory(s.mappedReservedWeightG, s.mappedReservedLengthM, preference)} mapped · ${formatInventory(s.unassignedReservedWeightG, s.unassignedReservedLengthM, preference)} unassigned`,
      icon: Layers3,
      onClick: () => onNavigate('jobs'),
    },
    {
      label: 'Low stock',
      value: `${s.lowStockSpools} spools`,
      note: `${s.loadedSpools} loaded`,
      icon: AlertTriangle,
    },
  ];
  return (
    <div className="space-y-7">
      <section className="flex flex-wrap items-center gap-2 rounded-2xl border bg-card p-3 shadow-sm">
        <span className="mr-2 text-sm font-semibold">Quick actions</span>
        <Button size="sm" onClick={onAddSpool}><Plus className="size-4" /> Add spool</Button>
        <Button size="sm" variant="outline" onClick={() => onNavigate('spools')}><Scale className="size-4" /> Weigh spool</Button>
        <Button size="sm" variant="outline" onClick={onAddPrinter}><PrinterIcon className="size-4" /> Add printer</Button>
        <Button size="sm" variant="outline" onClick={() => onNavigate('jobs')}><Inbox className="size-4" /> Process job</Button>
      </section>
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {metrics.map(({ label, value, note, icon: Icon, onClick }) => {
          const content = <>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-muted-foreground">
                {label}
              </p>
              <span className="grid size-9 place-items-center rounded-xl bg-secondary">
                <Icon className="size-4 text-primary" />
              </span>
            </div>
            <p className="mt-4 text-2xl font-bold tracking-tight">{value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{note}</p>
          </>;
          return onClick
            ? <button key={label} type="button" onClick={onClick} className="rounded-2xl border bg-card p-5 text-left shadow-sm transition hover:border-primary/50 hover:bg-accent/30">{content}</button>
            : <article key={label} className="rounded-2xl border bg-card p-5 text-left shadow-sm">{content}</article>;
        })}
      </section>
      <div className="grid gap-6 xl:grid-cols-2">
        <AttentionPanel status={dashboard.attention} summary={dashboard.summary} onNavigate={onNavigate} />
        <ReorderPanel reorder={dashboard.reorder} onNavigate={onNavigate} />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.35fr_.65fr]">
        <section className="rounded-2xl border bg-card shadow-sm">
          <PanelHeader
            title="Active spools"
            action="View all"
            onClick={() => onNavigate('spools')}
          />
          <div className="grid gap-3 p-4 md:grid-cols-3">
            {dashboard.spools.length ? (
              dashboard.spools
                .slice(0, 3)
                .map((spool) => <SpoolCard key={spool.id} spool={spool} preference={preference} />)
            ) : (
              <Empty text="No spools yet." />
            )}
          </div>
        </section>
        <section className="rounded-2xl border bg-card shadow-sm">
          <PanelHeader
            title="Print inbox"
            action={`${dashboard.jobs.length} open`}
            onClick={() => onNavigate('jobs')}
          />
          <div className="divide-y">
            {dashboard.jobs.length ? (
              dashboard.jobs.slice(0, 4).map((job) => (
                <button
                  key={job.id}
                  onClick={() => onJob(job)}
                  className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-muted/60"
                >
                  <span
                    className={`size-2.5 rounded-full ${job.status === 'NEEDS_REVIEW' ? 'bg-orange-500' : 'bg-emerald-500'}`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">
                      {job.displayName}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {job.printer.code} · {job.printer.name}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold">
                      {formatWeight(
                        job.usages.reduce(
                          (sum, u) => sum + u.estimatedWeightG,
                          0,
                        ),
                      )}
                    </p>
                    <p className="text-[11px] text-muted-foreground">
                      {job.status}
                    </p>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </button>
              ))
            ) : (
              <Empty text="No open print jobs." />
            )}
          </div>
        </section>
      </div>
      <PrinterPanel
        printers={dashboard.printers}
        onAll={() => onNavigate('printers')}
      />
      <TrendPanel key={`${s.remainingWeightG}-${s.openJobs}`} />
    </div>
  );
}

function AttentionPanel({ status, summary, onNavigate }: { status: OperationalStatus; summary: Dashboard['summary']; onNavigate: (key: NavKey) => void }) {
  const rows = [
    { label: 'Low-stock spools', value: summary.lowStockSpools, target: 'spools' as NavKey },
    { label: 'Negative inventory', value: summary.negativeSpools, target: 'spools' as NavKey },
    { label: 'Jobs older than 7 days', value: status.staleJobs, target: 'jobs' as NavKey },
    { label: 'Unknown slicer profiles', value: status.unknownProfiles, target: 'jobs' as NavKey },
    { label: status.catalog.failed ? 'Catalog synchronization failed' : 'Catalog needs attention', value: status.catalog.stale || status.catalog.failed ? 1 : 0, target: 'settings' as NavKey },
    { label: 'Backup needs attention', value: status.backup.stale ? 1 : 0, target: 'settings' as NavKey },
  ].filter((row) => row.value > 0);
  return (
    <section className="rounded-2xl border bg-card shadow-sm">
      <PanelHeader title="Needs attention" action={`${rows.length} items`} onClick={() => onNavigate(rows[0]?.target ?? 'overview')} />
      <div className="divide-y">
        {rows.length ? rows.slice(0, 6).map((row) => (
          <button key={row.label} onClick={() => onNavigate(row.target)} className="flex w-full items-center justify-between px-5 py-3 text-left hover:bg-muted/60">
            <span className="flex items-center gap-2 text-sm"><AlertTriangle className="size-4 text-orange-500" />{row.label}</span>
            <Badge variant="secondary">{row.value}</Badge>
          </button>
        )) : <Empty text="Everything looks current." />}
      </div>
    </section>
  );
}

function ReorderPanel({ reorder, onNavigate }: { reorder: ReorderPayload; onNavigate: (key: NavKey) => void }) {
  return (
    <section className="rounded-2xl border bg-card shadow-sm">
      <PanelHeader title="Reorder suggestions" action={`${reorder.groups.length} products`} onClick={() => onNavigate('spools')} />
      <div className="divide-y">
        {reorder.groups.length ? reorder.groups.slice(0, 5).map((group) => (
          <div key={group.productKey} className="flex items-center gap-3 px-5 py-3">
            <span className="size-8 shrink-0 rounded-lg border" style={{ background: group.colorHex }} />
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{group.brand} · {group.materialName}</p><p className="text-xs text-muted-foreground">{group.spoolCount} spools · {formatWeight(group.availableWeightG)} available</p></div>
            <Badge variant="outline">-{formatWeight(group.shortageG)}</Badge>
          </div>
        )) : <Empty text={`All products are above ${formatWeight(reorder.defaultThresholdG)}.`} />}
      </div>
    </section>
  );
}
function SpoolCard({ spool, preference = 'both', onOpen }: { spool: Spool; preference?: User['preferredUnit']; onOpen?: () => void }) {
  return (
    <button type="button" disabled={!onOpen} className="w-full rounded-2xl border bg-background p-4 text-left disabled:cursor-default disabled:opacity-100" onClick={onOpen}>
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span
            className="size-9 rounded-xl border-4 border-white shadow ring-1 ring-border"
            style={{ background: spool.colorHex }}
          />
          <div>
            <p className="text-sm font-bold">{spool.brand}</p>
            <p className="text-xs text-muted-foreground">
              {spool.materialName}
            </p>
          </div>
        </div>
        <Badge variant="secondary" className="font-mono text-[10px]">
          {spool.code}
        </Badge>
      </div>
      <div className="mt-6 flex items-end justify-between">
        <div>
          <p className="text-2xl font-bold">{spool.remainingPercent}%</p>
          <p className="text-xs text-muted-foreground">
            {formatInventory(spool.remainingWeightG, spool.remainingLengthM, preference)}
          </p>
        </div>
        <span
          className={`text-xs font-semibold ${spool.archived ? 'text-muted-foreground' : spool.lowStock ? 'text-orange-600' : 'text-emerald-600'}`}
        >
          {spool.archived ? 'Inactive' : spool.lowStock ? 'Low' : 'Available'}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-1 text-[10px]">
        <div><p className="text-muted-foreground">Remaining</p><p className="truncate font-semibold">{formatInventory(spool.remainingWeightG, spool.remainingLengthM, preference)}</p></div>
        <div><p className="text-muted-foreground">Reserved</p><p className="truncate font-semibold">{formatInventory(spool.reservedWeightG, spool.reservedLengthM, preference)}</p></div>
        <div><p className="text-muted-foreground">Available</p><p className="truncate font-semibold">{formatInventory(spool.availableWeightG, spool.availableLengthM, preference)}</p></div>
      </div>
      <div className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-muted" aria-label={`${spool.remainingPercent}% remaining`}>
        <span className="h-full bg-emerald-500" style={{ width: `${Math.max(0, Math.min(100, spool.initialWeightG ? spool.availableWeightG / spool.initialWeightG * 100 : 0))}%` }} />
        <span className="h-full bg-orange-500" style={{ width: `${Math.max(0, Math.min(100, spool.initialWeightG ? spool.reservedWeightG / spool.initialWeightG * 100 : 0))}%` }} />
      </div>
      {spool.loadedOn && (
        <p className="mt-3 truncate text-[11px] text-muted-foreground">
          Loaded: {spool.loadedOn.printerCode} · {spool.loadedOn.tool}
        </p>
      )}
    </button>
  );
}
function PrinterPanel({
  printers,
  onAll,
}: {
  printers: Printer[];
  onAll: () => void;
}) {
  return (
    <section className="rounded-2xl border bg-card shadow-sm">
      <PanelHeader title="Printer loadouts" action="Manage" onClick={onAll} />
      <div className="grid gap-4 p-4 md:grid-cols-2">
        {printers.length ? (
          printers.slice(0, 4).map((printer, index) => (
            <article
              key={printer.id}
              className={`rounded-2xl p-5 ${index === 0 ? 'bg-[#15231f] text-white' : 'border'}`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p
                    className={`text-xs ${index === 0 ? 'text-white/55' : 'text-muted-foreground'}`}
                  >
                    {printer.code}
                  </p>
                  <h3 className="font-bold">{printer.name}</h3>
                </div>
                <Badge variant={index === 0 ? 'default' : 'secondary'}>
                  {printer.tools.length} tools
                </Badge>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-8">
                {printer.tools.map((tool) => (
                  <div
                    key={tool.id}
                    className={`rounded-xl p-2 ${index === 0 ? 'bg-white/7' : 'bg-muted'}`}
                  >
                    <span
                      className="mx-auto block size-6 rounded-lg border"
                      style={{
                        background: tool.loadedSpool?.colorHex || 'transparent',
                      }}
                    />
                    <p
                      className={`mt-2 text-center text-[10px] ${index === 0 ? 'text-white/65' : 'text-muted-foreground'}`}
                    >
                      {tool.label}
                    </p>
                  </div>
                ))}
              </div>
            </article>
          ))
        ) : (
          <Empty text="No printers yet." />
        )}
      </div>
    </section>
  );
}
function TrendPanel() {
  const [usage, setUsage] = useState<UsageAnalytics | null>(null);
  useEffect(() => {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    api<UsageAnalytics>(`/api/analytics/usage?days=30&timezone=${encodeURIComponent(timezone)}`)
      .then(setUsage)
      .catch(() => setUsage(null));
  }, []);
  const data = usage?.points.map((point) => ({
    ...point,
    label: new Date(`${point.date}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  })) ?? [];
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-bold">Usage — last 30 days</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {formatWeight(usage?.totals.weightG ?? 0)} · {formatLength(usage?.totals.lengthM ?? 0)} booked
          </p>
        </div>
        <Badge variant="secondary">30 days</Badge>
      </div>
      <div className="mt-5 h-64 w-full">
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={256}>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="label" minTickGap={28} tick={{ fontSize: 11 }} />
            <YAxis yAxisId="grams" tick={{ fontSize: 11 }} width={46} unit=" g" />
            <YAxis yAxisId="meters" orientation="right" tick={{ fontSize: 11 }} width={46} unit=" m" />
            <Tooltip formatter={(value, name) => [`${Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })} ${name === 'Weight' ? 'g' : 'm'}`, name]} />
            <Legend />
            <Line yAxisId="grams" type="monotone" dataKey="weightG" name="Weight" stroke="var(--color-chart-1)" strokeWidth={2} dot={false} />
            <Line yAxisId="meters" type="monotone" dataKey="lengthM" name="Length" stroke="var(--color-chart-2)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
function PanelHeader({
  title,
  action,
  onClick,
}: {
  title: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b px-5 py-4">
      <h2 className="font-bold">{title}</h2>
      <Button variant="ghost" size="sm" onClick={onClick}>
        {action}
        <ChevronRight className="size-4" />
      </Button>
    </div>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="col-span-full p-8 text-center text-sm text-muted-foreground">
      {text}
    </div>
  );
}

function SpoolsView({
  spools,
  preference,
  isAdmin,
  onRefresh,
  onAdd,
  onDuplicate,
}: {
  spools: Spool[];
  preference: User['preferredUnit'];
  isAdmin: boolean;
  onRefresh: () => Promise<void>;
  onAdd: () => void;
  onDuplicate: (spool: Spool) => void;
}) {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SpoolFilters>(EMPTY_SPOOL_FILTERS);
  const [weigh, setWeigh] = useState<Spool | null>(null);
  const [emptySpool, setEmptySpool] = useState<Spool | null>(null);
  const [editingSpool, setEditingSpool] = useState<Spool | null>(null);
  const [repurposeSpool, setRepurposeSpool] = useState<Spool | null>(null);
  const [archivedSpools, setArchivedSpools] = useState<Spool[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [loadingArchived, setLoadingArchived] = useState(false);
  const [listError, setListError] = useState('');
  const [view, setView] = useState<'cards' | 'table'>(() => (typeof window !== 'undefined' && localStorage.getItem('filaflow.spoolView') === 'table' ? 'table' : 'cards'));
  const [selectedSpool, setSelectedSpool] = useState<Spool | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [tableSort, setTableSort] = useState<{ key: SpoolColumn; direction: 'asc' | 'desc' }>({ key: 'code', direction: 'asc' });
  const [similarIds, setSimilarIds] = useState<Set<string> | null>(null);
  const [columns, setColumns] = useState<Set<SpoolColumn>>(() => {
    try {
      const saved = typeof window === 'undefined' ? null : JSON.parse(localStorage.getItem('filaflow.spoolColumns') || 'null') as SpoolColumn[] | null;
      return new Set(saved?.length ? saved : SPOOL_COLUMNS.map((column) => column.key));
    } catch { return new Set(SPOOL_COLUMNS.map((column) => column.key)); }
  });
  const [savedFilters, setSavedFilters] = useState<Record<string, SpoolFilters>>(() => {
    try { return typeof window === 'undefined' ? {} : JSON.parse(localStorage.getItem('filaflow.savedFilters') || '{}') as Record<string, SpoolFilters>; } catch { return {}; }
  });
  const visibleSpools = showArchived ? archivedSpools : spools;
  const filterOptions = useMemo(() => {
    const unique = (values: string[]) =>
      [...new Set(values.filter(Boolean))].sort((a, b) =>
        a.localeCompare(b, undefined, { sensitivity: 'base' }),
      );
    const colors = new Map<string, { value: string; label: string }>();
    for (const spool of visibleSpools) {
      const value = spool.colorName?.trim().toLowerCase();
      if (value && !colors.has(value)) {
        colors.set(value, {
          value,
          label: spool.colorName.trim(),
        });
      }
    }
    return {
      brands: unique(visibleSpools.map((spool) => spool.brand)),
      materials: unique(visibleSpools.map((spool) => spool.materialType)),
      colors: [...colors.values()].sort((a, b) =>
        a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }),
      ),
      locations: unique(visibleSpools.map((spool) => spool.location)),
      printers: unique(
        visibleSpools
          .map((spool) => spool.loadedOn?.printerCode ?? '')
          .filter(Boolean),
      ),
    };
  }, [visibleSpools]);
  useEffect(() => {
    if (!filters.similarColor) return;
    const timer = setTimeout(() => {
      api<Spool[]>(`/api/spools?colorHex=${encodeURIComponent(filters.similarColor)}&deltaE=${encodeURIComponent(filters.deltaE)}&archived=${showArchived}`)
        .then((rows) => setSimilarIds(new Set(rows.map((row) => row.id))))
        .catch(() => setSimilarIds(new Set()));
    }, 180);
    return () => clearTimeout(timer);
  }, [filters.deltaE, filters.similarColor, showArchived]);
  const filtered = useMemo(
    () =>
      visibleSpools.filter((spool) => {
        const haystack = `${spool.code} ${spool.brand} ${spool.materialName} ${spool.materialType} ${spool.colorName} ${spool.colorHex} ${spool.location} ${spool.lotNumber} ${spool.serialNumber} ${spool.loadedOn?.printer ?? ''} ${spool.loadedOn?.printerCode ?? ''}`.toLowerCase();
        const matchesQuery = query.trim().toLowerCase().split(/\s+/).filter(Boolean).every((token) => haystack.includes(token));
        return (
          matchesQuery &&
          (!filters.brand || spool.brand === filters.brand) &&
          (!filters.material || spool.materialType === filters.material) &&
          (!filters.color ||
            spool.colorName?.trim().toLowerCase() === filters.color) &&
          (!filters.location || spool.location === filters.location) &&
          (!filters.loadState ||
            (filters.loadState === 'loaded'
              ? !!spool.loadedOn
              : !spool.loadedOn)) &&
          (!filters.stockState ||
            (filters.stockState === 'low' ? spool.lowStock : !spool.lowStock)) &&
          (!filters.printer || spool.loadedOn?.printerCode === filters.printer)
          && (!similarIds || similarIds.has(spool.id))
        );
      }),
    [visibleSpools, query, filters, similarIds],
  );
  const activeFilterCount = Object.entries(filters).filter(([key, value]) => key !== 'deltaE' && Boolean(value)).length;
  const tableRows = useMemo(() => {
    const value = (spool: Spool) => {
      const values: Record<SpoolColumn, string | number> = {
        code: spool.code, color: spool.colorName, brand: spool.brand, filament: spool.materialName,
        material: spool.materialType, remaining: spool.remainingWeightG, reserved: spool.reservedWeightG,
        available: spool.availableWeightG, location: spool.location, loadout: spool.loadedOn ? `${spool.loadedOn.printerCode} ${spool.loadedOn.tool}` : '', status: spool.archived ? 'archived' : spool.lowStock ? 'low' : 'available',
      };
      return values[tableSort.key];
    };
    return [...filtered].sort((left, right) => {
      const a = value(left); const b = value(right);
      const result = typeof a === 'number' && typeof b === 'number' ? a - b : String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' });
      return tableSort.direction === 'asc' ? result : -result;
    });
  }, [filtered, tableSort]);
  function sortTable(key: SpoolColumn) { setTableSort((current) => ({ key, direction: current.key === key && current.direction === 'asc' ? 'desc' : 'asc' })); }
  function updateFilter(key: keyof SpoolFilters, value: string) {
    if (key === 'similarColor' && !value) setSimilarIds(null);
    setFilters((current) => ({ ...current, [key]: value }));
  }
  function clearFilters() {
    setQuery('');
    setFilters({ ...EMPTY_SPOOL_FILTERS });
  }
  function changeView(next: 'cards' | 'table') { setView(next); localStorage.setItem('filaflow.spoolView', next); }
  function toggleColumn(key: SpoolColumn) {
    setColumns((current) => {
      const next = new Set(current);
      if (next.has(key) && next.size > 1) next.delete(key); else next.add(key);
      localStorage.setItem('filaflow.spoolColumns', JSON.stringify([...next]));
      return next;
    });
  }
  function saveFilter() {
    const name = prompt('Name this filter');
    if (!name?.trim()) return;
    const next = { ...savedFilters, [name.trim()]: filters };
    setSavedFilters(next); localStorage.setItem('filaflow.savedFilters', JSON.stringify(next));
  }
  function printSelected() {
    if (!selectedIds.size) return;
    window.open(`/labels/print?spools=${encodeURIComponent([...selectedIds].join(','))}`, '_blank');
  }
  async function toggleArchived() {
    if (!showArchived) {
      setLoadingArchived(true);
      try {
        setArchivedSpools(await api<Spool[]>('/api/spools?archived=true'));
        setShowArchived(true);
        setFilters({ ...EMPTY_SPOOL_FILTERS });
        setListError('');
      } catch (reason) {
        setListError(
          reason instanceof Error ? reason.message : 'Could not load archived spools',
        );
      } finally {
        setLoadingArchived(false);
      }
    } else {
      setShowArchived(false);
      setFilters({ ...EMPTY_SPOOL_FILTERS });
    }
  }
  return (
    <div className="space-y-5">
      <div className="rounded-2xl border bg-card p-3 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search spools"
            className="h-10 pl-9"
          />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{filtered.length} shown</Badge>
            {!showArchived && (
              <Badge variant="outline">
                {spools.filter((spool) => spool.lowStock).length} low
              </Badge>
            )}
            <Button
              size="sm"
              variant={showArchived ? 'secondary' : 'outline'}
              onClick={toggleArchived}
              disabled={loadingArchived}
            >
              <Archive className="size-4" />
              {showArchived ? 'Show active' : 'Archived'}
            </Button>
            <div className="flex rounded-lg border p-0.5">
              <Button aria-label="Card view" size="icon-sm" variant={view === 'cards' ? 'secondary' : 'ghost'} onClick={() => changeView('cards')}><LayoutGrid className="size-4" /></Button>
              <Button aria-label="Table view" size="icon-sm" variant={view === 'table' ? 'secondary' : 'ghost'} onClick={() => changeView('table')}><TableProperties className="size-4" /></Button>
            </div>
            {view === 'table' && <DropdownMenu><DropdownMenuTrigger render={<Button size="sm" variant="outline" />}><SlidersHorizontal className="size-4" /> Columns</DropdownMenuTrigger><DropdownMenuContent align="end" className="w-48">{SPOOL_COLUMNS.map((column) => <DropdownMenuCheckboxItem key={column.key} checked={columns.has(column.key)} onCheckedChange={() => toggleColumn(column.key)}>{column.label}</DropdownMenuCheckboxItem>)}</DropdownMenuContent></DropdownMenu>}
            {selectedIds.size > 0 && <Button size="sm" onClick={printSelected}><Download className="size-4" /> Print {selectedIds.size}</Button>}
          </div>
        </div>
        <div className="mt-3 border-t pt-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
              <SlidersHorizontal className="size-3.5" /> Filters
              {activeFilterCount > 0 && (
                <Badge variant="secondary" className="h-5 px-1.5 text-[10px]">
                  {activeFilterCount}
                </Badge>
              )}
            </div>
            {(activeFilterCount > 0 || query) && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="size-3.5" /> Clear
              </Button>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-7">
            <NativeSelect
              aria-label="Filter by brand"
              className="w-full"
              value={filters.brand}
              onChange={(event) => updateFilter('brand', event.target.value)}
            >
              <NativeSelectOption value="">All brands</NativeSelectOption>
              {filterOptions.brands.map((brand) => (
                <NativeSelectOption key={brand} value={brand}>
                  {brand}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Filter by material"
              className="w-full"
              value={filters.material}
              onChange={(event) =>
                updateFilter('material', event.target.value)
              }
            >
              <NativeSelectOption value="">All materials</NativeSelectOption>
              {filterOptions.materials.map((material) => (
                <NativeSelectOption key={material} value={material}>
                  {material}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Filter by color"
              className="w-full"
              value={filters.color}
              onChange={(event) => updateFilter('color', event.target.value)}
            >
              <NativeSelectOption value="">All colors</NativeSelectOption>
              {filterOptions.colors.map((color) => (
                <NativeSelectOption key={color.value} value={color.value}>
                  {color.label}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Filter by location"
              className="w-full"
              value={filters.location}
              onChange={(event) =>
                updateFilter('location', event.target.value)
              }
            >
              <NativeSelectOption value="">All locations</NativeSelectOption>
              {filterOptions.locations.map((location) => (
                <NativeSelectOption key={location} value={location}>
                  {location}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <NativeSelect
              aria-label="Filter by load state"
              className="w-full"
              value={filters.loadState}
              onChange={(event) =>
                updateFilter('loadState', event.target.value)
              }
            >
              <NativeSelectOption value="">Loaded or unloaded</NativeSelectOption>
              <NativeSelectOption value="loaded">Loaded</NativeSelectOption>
              <NativeSelectOption value="unloaded">Unloaded</NativeSelectOption>
            </NativeSelect>
            <NativeSelect
              aria-label="Filter by stock state"
              className="w-full"
              value={filters.stockState}
              onChange={(event) =>
                updateFilter('stockState', event.target.value)
              }
            >
              <NativeSelectOption value="">All stock levels</NativeSelectOption>
              <NativeSelectOption value="low">Low stock</NativeSelectOption>
              <NativeSelectOption value="healthy">Stock available</NativeSelectOption>
            </NativeSelect>
            <NativeSelect
              aria-label="Filter by printer"
              className="w-full"
              value={filters.printer}
              onChange={(event) => updateFilter('printer', event.target.value)}
            >
              <NativeSelectOption value="">All printers</NativeSelectOption>
              {filterOptions.printers.map((printer) => (
                <NativeSelectOption key={printer} value={printer}>
                  {printer}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <div className="space-y-1"><Label htmlFor="similar-color" className="text-[11px]">Similar to color</Label><Input id="similar-color" type="color" className="h-9 w-14 p-1" value={filters.similarColor || '#808080'} onChange={(event) => updateFilter('similarColor', event.target.value)} /></div>
            {filters.similarColor && <><div className="space-y-1"><Label htmlFor="color-distance" className="text-[11px]">Color distance</Label><Input id="color-distance" className="h-9 w-20" type="number" min="2" max="30" value={filters.deltaE} onChange={(event) => updateFilter('deltaE', event.target.value)} /></div><Button size="sm" variant="ghost" onClick={() => updateFilter('similarColor', '')}>Disable color match</Button></>}
            <Button size="sm" variant="outline" onClick={saveFilter}><Save className="size-3.5" /> Save filter</Button>
            {Object.entries(savedFilters).map(([name, saved]) => <Button key={name} size="sm" variant="ghost" onClick={() => setFilters(saved)}>{name}</Button>)}
          </div>
        </div>
      </div>
      {listError && <p className="text-sm text-destructive">{listError}</p>}
      {view === 'cards' ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {filtered.map((spool) => (
          <article
            key={spool.id}
            className="rounded-2xl border bg-card p-1 shadow-sm"
          >
            <SpoolCard spool={spool} preference={preference} onOpen={() => setSelectedSpool(spool)} />
            <div className="flex items-center gap-2 p-3 pt-0">
              {!spool.archived && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setWeigh(spool)}
                >
                  <Scale className="size-4" /> Weigh
                </Button>
              )}
              <DropdownMenu><DropdownMenuTrigger render={<Button aria-label={`Actions for ${spool.code}`} variant="ghost" size="icon-sm" className="ml-auto" />}><Ellipsis className="size-4" /></DropdownMenuTrigger><DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setEditingSpool(spool)}><Pencil className="size-4" /> Edit</DropdownMenuItem>
                <DropdownMenuItem onClick={() => onDuplicate(spool)}><Copy className="size-4" /> Duplicate</DropdownMenuItem>
                <DropdownMenuItem onClick={() => window.open(`/labels/print?spools=${spool.id}`, '_blank')}><Download className="size-4" /> Label</DropdownMenuItem>
                {!spool.archived && <DropdownMenuItem className="text-destructive" onClick={() => setEmptySpool(spool)}><Archive className="size-4" /> Empty</DropdownMenuItem>}
                {spool.archived && isAdmin && <DropdownMenuItem onClick={() => setRepurposeSpool(spool)}><RotateCcw className="size-4" /> Restore &amp; repurpose</DropdownMenuItem>}
              </DropdownMenuContent></DropdownMenu>
            </div>
          </article>
        ))}
        {!filtered.length && <Empty text="No spools found." />}
      </div> : <div className="overflow-x-auto rounded-2xl border bg-card shadow-sm">
        <table className="w-full min-w-[980px] text-sm"><thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground"><tr>
          <th className="p-3"><input aria-label="Select all shown spools" type="checkbox" checked={tableRows.length > 0 && tableRows.every((row) => selectedIds.has(row.id))} onChange={(event) => setSelectedIds(event.target.checked ? new Set(tableRows.map((row) => row.id)) : new Set())} /></th>
          {SPOOL_COLUMNS.filter((column) => columns.has(column.key)).map((column) => <th key={column.key} className="p-3 font-semibold"><button type="button" onClick={() => sortTable(column.key)} className="inline-flex items-center gap-1 hover:text-foreground">{column.label}{tableSort.key === column.key ? (tableSort.direction === 'asc' ? ' ↑' : ' ↓') : ''}</button></th>)}
          {showArchived && isAdmin && <th className="p-3 font-semibold">Actions</th>}
        </tr></thead><tbody className="divide-y">{tableRows.map((spool) => <tr key={spool.id} className="hover:bg-muted/40">
          <td className="p-3" onClick={(event) => event.stopPropagation()}><input aria-label={`Select ${spool.code}`} type="checkbox" checked={selectedIds.has(spool.id)} onChange={(event) => setSelectedIds((current) => { const next = new Set(current); if (event.target.checked) next.add(spool.id); else next.delete(spool.id); return next; })} /></td>
          {columns.has('code') && <td className="p-3 font-mono font-semibold"><button onClick={() => setSelectedSpool(spool)} className="underline-offset-2 hover:underline">{spool.code}</button></td>}{columns.has('color') && <td className="p-3"><span aria-label={spool.colorName} className="block size-6 rounded-md border" style={{ background: spool.colorHex }} /></td>}
          {columns.has('brand') && <td className="p-3 font-semibold">{spool.brand}</td>}{columns.has('filament') && <td className="p-3">{spool.materialName}</td>}{columns.has('material') && <td className="p-3">{spool.materialType}</td>}
          {columns.has('remaining') && <td className="p-3">{formatInventory(spool.remainingWeightG, spool.remainingLengthM, preference)}</td>}{columns.has('reserved') && <td className="p-3">{formatInventory(spool.reservedWeightG, spool.reservedLengthM, preference)}</td>}{columns.has('available') && <td className="p-3 font-semibold">{formatInventory(spool.availableWeightG, spool.availableLengthM, preference)}</td>}
          {columns.has('location') && <td className="p-3">{spool.location || '—'}</td>}{columns.has('loadout') && <td className="p-3">{spool.loadedOn ? `${spool.loadedOn.printerCode} · ${spool.loadedOn.tool}` : 'Unloaded'}</td>}{columns.has('status') && <td className="p-3">{spool.lowStock ? <Badge variant="outline">Low</Badge> : <Badge variant="secondary">Available</Badge>}</td>}
          {showArchived && isAdmin && <td className="p-3"><Button size="sm" variant="outline" onClick={() => setRepurposeSpool(spool)}><RotateCcw className="size-3.5" /> Restore</Button></td>}
        </tr>)}</tbody></table>{!filtered.length && <Empty text="No spools found." />}
      </div>}
      <Button
        onClick={onAdd}
        className="fixed bottom-20 right-5 rounded-full shadow-lg lg:hidden"
        size="icon"
      >
        <Plus />
      </Button>
      <WeighDialog
        spool={weigh}
        open={!!weigh}
        onOpenChange={(open) => !open && setWeigh(null)}
        onUpdated={async () => {
          setWeigh(null);
          await onRefresh();
        }}
      />
      <EmptySpoolDialog
        spool={emptySpool}
        open={!!emptySpool}
        onOpenChange={(open) => !open && setEmptySpool(null)}
        onUpdated={async () => {
          setEmptySpool(null);
          setShowArchived(false);
          await onRefresh();
        }}
      />
      <EditSpoolDialog
        spool={editingSpool}
        open={!!editingSpool}
        onOpenChange={(open) => !open && setEditingSpool(null)}
        onUpdated={async () => { setEditingSpool(null); await onRefresh(); }}
      />
      <RepurposeSpoolDialog
        key={repurposeSpool?.id ?? 'closed'}
        spool={repurposeSpool}
        open={!!repurposeSpool}
        onOpenChange={(open) => !open && setRepurposeSpool(null)}
        onUpdated={async () => {
          setRepurposeSpool(null);
          setShowArchived(false);
          await onRefresh();
        }}
      />
      <SpoolDetailSheet spool={selectedSpool} open={!!selectedSpool} onOpenChange={(open) => !open && setSelectedSpool(null)} preference={preference} />
    </div>
  );
}
function SpoolDetailSheet({ spool, open, onOpenChange, preference }: { spool: Spool | null; open: boolean; onOpenChange: (open: boolean) => void; preference: User['preferredUnit'] }) {
  const [detail, setDetail] = useState<(Spool & { ledger: Array<{ id: string; kind: string; weightDeltaG: number; lengthDeltaM: number; note: string; createdAt: string }> }) | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  useEffect(() => {
    if (!spool || !open) return;
    Promise.all([
      api<Spool & { ledger: Array<{ id: string; kind: string; weightDeltaG: number; lengthDeltaM: number; note: string; createdAt: string }> }>(`/api/spools/${spool.id}`),
      api<ActivityItem[]>(`/api/activity?entity_type=spool&entity_id=${spool.id}`),
    ]).then(([row, events]) => { setDetail(row); setActivity(events); }).catch(() => undefined);
  }, [open, spool]);
  const row = detail ?? spool;
  return <Sheet open={open} onOpenChange={onOpenChange}><SheetContent className="w-full overflow-y-auto sm:max-w-xl">
    <SheetHeader><SheetTitle>{row?.code} · {row?.brand}</SheetTitle><SheetDescription>{row?.materialName} · {row?.materialType}</SheetDescription></SheetHeader>
    {row && <div className="space-y-5 px-4 pb-6">
      <div className="flex items-center gap-4 rounded-2xl border p-4"><span className="size-14 rounded-2xl border" style={{ background: row.colorHex }} /><div><p className="font-semibold">{row.colorName}</p><p className="font-mono text-xs text-muted-foreground">{row.colorHex}</p></div></div>
      <div className="grid grid-cols-3 gap-2">{[
        ['Remaining', formatInventory(row.remainingWeightG, row.remainingLengthM, preference)],
        ['Reserved', formatInventory(row.reservedWeightG, row.reservedLengthM, preference)],
        ['Available', formatInventory(row.availableWeightG, row.availableLengthM, preference)],
      ].map(([label, value]) => <div key={label} className="rounded-xl bg-muted p-3"><p className="text-[11px] text-muted-foreground">{label}</p><p className="mt-1 text-sm font-bold">{value}</p></div>)}</div>
      <div className="grid grid-cols-2 gap-3 text-sm"><div><p className="text-xs text-muted-foreground">Location</p><p>{row.location || '—'}</p></div><div><p className="text-xs text-muted-foreground">Loaded on</p><p>{row.loadedOn ? `${row.loadedOn.printerCode} · ${row.loadedOn.tool}` : 'Unloaded'}</p></div><div><p className="text-xs text-muted-foreground">Diameter / density</p><p>{row.diameterMm} mm · {row.density} g/cm³</p></div><div><p className="text-xs text-muted-foreground">Spool tare</p><p>{formatWeight(row.tareWeightG)}</p></div></div>
      {detail && <section><h3 className="font-semibold">Inventory ledger</h3><div className="mt-2 divide-y rounded-xl border">{detail.ledger.slice(0, 20).map((entry) => <div key={entry.id} className="flex justify-between gap-3 p-3"><div><p className="text-sm font-medium">{entry.kind}</p><p className="text-xs text-muted-foreground">{entry.note} · {new Date(entry.createdAt).toLocaleString()}</p></div><p className="whitespace-nowrap text-xs font-semibold">{formatWeight(entry.weightDeltaG)} · {formatLength(entry.lengthDeltaM)}</p></div>)}</div></section>}
      <section><h3 className="font-semibold">Activity</h3><div className="mt-2 space-y-2">{activity.slice(0, 12).map((event) => <div key={event.id} className="rounded-xl bg-muted/60 p-3"><p className="text-sm font-medium">{event.action.replaceAll('.', ' ')}</p><p className="text-xs text-muted-foreground">{new Date(event.createdAt).toLocaleString()}</p></div>)}</div></section>
    </div>}
  </SheetContent></Sheet>;
}
function PrintersView({
  printers,
  spools,
  preference,
  onRefresh,
}: {
  printers: Printer[];
  spools: Spool[];
  preference: User['preferredUnit'];
  onRefresh: () => Promise<void>;
}) {
  const [editingPrinter, setEditingPrinter] = useState<Printer | null>(null);
  const [optimistic, setOptimistic] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  async function load(printerId: string, toolId: string, spoolId: string) {
    const snapshot = { ...optimistic };
    const sourceToolId = spools.find((spool) => spool.id === spoolId)?.loadedOn?.toolId;
    setOptimistic((current) => {
      const next = { ...current, [toolId]: spoolId };
      if (sourceToolId && sourceToolId !== toolId) next[sourceToolId] = '';
      return next;
    }); setError('');
    try {
      await api(`/api/printers/${printerId}/tools/${toolId}/loadout`, { method: 'PUT', body: JSON.stringify({ spool_id: spoolId || null }) });
      await onRefresh();
      setOptimistic((current) => { const next = { ...current }; delete next[toolId]; if (sourceToolId) delete next[sourceToolId]; return next; });
    } catch (reason) {
      setOptimistic(snapshot);
      setError(reason instanceof Error ? reason.message : 'Loadout update failed');
    }
  }
  const orderedFor = (currentId: string | null) => [...spools].sort((left, right) => {
    const rank = (row: Spool) => row.id === currentId ? 0 : row.loadedOn ? 2 : 1;
    return rank(left) - rank(right) || right.availableWeightG - left.availableWeightG;
  });
  return (
    <div className="space-y-5">
      {error && <p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {printers.map((printer) => (
        <article
          key={printer.id}
          className="overflow-hidden rounded-2xl border bg-card shadow-sm"
        >
          <div className="flex items-center justify-between border-b p-5">
            <div>
              <p className="font-mono text-xs text-muted-foreground">
                {printer.code}
              </p>
              <h2 className="text-lg font-bold">{printer.name}</h2>
              <p className="text-xs text-muted-foreground">
                {printer.manufacturer} {printer.model} ·{' '}
                {printer.slicerProfile || 'No profile name'}
              </p>
              {printer.location && <p className="mt-1 text-xs text-muted-foreground">{printer.location}</p>}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={() => setEditingPrinter(printer)}><Pencil className="size-4" /> Edit</Button>
              <Badge>{printer.tools.length} tools</Badge>
            </div>
          </div>
          <div className={`grid gap-3 p-4 ${printer.tools.length >= 8 ? 'grid-cols-2 sm:grid-cols-4 xl:grid-cols-8' : 'sm:grid-cols-2'}`}>
            {printer.tools.map((tool) => (
              <div
                key={tool.id}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => { event.preventDefault(); const spoolId = event.dataTransfer.getData('application/x-filaflow-spool'); if (spoolId) void load(printer.id, tool.id, spoolId); }}
                className="rounded-2xl border bg-muted/40 p-3 transition hover:border-primary/50"
              >
                {(() => { const selectedId = Object.prototype.hasOwnProperty.call(optimistic, tool.id) ? optimistic[tool.id] : tool.loadedSpool?.id || ''; const selected = spools.find((row) => row.id === selectedId); return <>
                <div className="flex items-center justify-between">
                  <Badge variant="secondary" className="font-mono">{tool.label}</Badge><GripVertical className="size-4 text-muted-foreground" />
                </div>
                <div className="mt-4 text-center">
                  <span
                    className="mx-auto block size-10 rounded-xl border shadow-sm"
                    style={{
                      background: selected?.colorHex || 'transparent',
                    }}
                  />
                  <p className="mt-2 truncate text-xs font-semibold">{selected ? `${selected.code} · ${selected.materialType}` : 'No spool loaded'}</p>
                  <p className="truncate text-[10px] text-muted-foreground">{selected ? formatInventory(selected.availableWeightG, selected.availableLengthM, preference) : 'Drop a spool here'}</p>
                </div>
                <select
                  aria-label={`${printer.code} ${tool.label} spool`}
                  className="mt-3 h-9 w-full rounded-lg border bg-background px-2 text-xs"
                  value={selectedId}
                  onChange={(e) => load(printer.id, tool.id, e.target.value)}
                >
                  <option value="">No spool loaded</option>
                  {orderedFor(selectedId).map((spool) => (
                    <option key={spool.id} value={spool.id}>
                      {spool.code} · {spool.brand} {spool.materialName} ·{' '}
                      {formatInventory(spool.availableWeightG, spool.availableLengthM, preference)}{spool.loadedOn && spool.id !== selectedId ? ` · loaded ${spool.loadedOn.printerCode}/${spool.loadedOn.tool}` : ''}
                    </option>
                  ))}
                </select>
                </>; })()}
              </div>
            ))}
          </div>
        </article>
      ))}
      {!printers.length && (
        <Empty text="No printers configured." />
      )}
      {!!spools.length && <section className="rounded-2xl border bg-card p-4 shadow-sm"><div className="mb-3"><h2 className="font-bold">Spool tray</h2><p className="text-xs text-muted-foreground">Drag a spool onto a tool slot, or use the selector.</p></div><div className="flex gap-2 overflow-x-auto pb-2">{spools.map((spool) => <button type="button" aria-label={`Drag ${spool.code} to a tool`} key={spool.id} draggable onDragStart={(event) => { event.dataTransfer.setData('application/x-filaflow-spool', spool.id); event.dataTransfer.effectAllowed = 'move'; }} className="flex min-w-48 items-center gap-2 rounded-xl border bg-background p-2 text-left active:cursor-grabbing"><span className="size-8 shrink-0 rounded-lg border" style={{ background: spool.colorHex }} /><span className="min-w-0"><span className="block truncate text-xs font-semibold">{spool.code} · {spool.materialType}</span><span className="block truncate text-[10px] text-muted-foreground">{formatInventory(spool.availableWeightG, spool.availableLengthM, preference)}</span></span></button>)}</div></section>}
      <EditPrinterDialog printer={editingPrinter} open={!!editingPrinter} onOpenChange={(open) => !open && setEditingPrinter(null)} onUpdated={async () => { setEditingPrinter(null); await onRefresh(); }} />
    </div>
  );
}
function JobsView({
  jobs,
  onSelect,
}: {
  jobs: Job[];
  onSelect: (job: Job) => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 60000); return () => window.clearInterval(timer); }, []);
  const age = (value: string) => {
    const minutes = Math.max(0, Math.floor((now - new Date(value).getTime()) / 60000));
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return hours < 48 ? `${hours}h ago` : `${Math.floor(hours / 24)}d ago`;
  };
  return (
    <div className="space-y-3">
      {jobs.map((job) => (
        <button
          key={job.id}
          onClick={() => onSelect(job)}
          className="grid w-full gap-4 rounded-2xl border bg-card p-5 text-left shadow-sm transition hover:border-primary/40 md:grid-cols-[1fr_auto_auto]"
        >
          <div>
            <div className="flex items-center gap-2">
              <Badge
                variant={
                  job.status === 'BOOKED'
                    ? 'secondary'
                    : job.status === 'NEEDS_REVIEW'
                      ? 'destructive'
                      : 'default'
                }
              >
                {job.status}
              </Badge>
              <span className="font-mono text-xs text-muted-foreground">
                {job.code}
              </span>
            </div>
            <h2 className="mt-2 font-bold">{job.displayName}</h2>
            <p className="text-xs text-muted-foreground">
              {job.printer.code} · {job.filename} · {age(job.createdAt)}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{job.slicerProfile || 'Unknown profile'} · {job.routingMode}</p>
          </div>
          <div>
            <p className="text-sm font-semibold">
              {job.usages.length} tool{job.usages.length === 1 ? '' : 's'}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatWeight(
                job.usages.reduce((s, u) => s + u.estimatedWeightG, 0),
              )} · {formatLength(job.usages.reduce((s, u) => s + u.estimatedLengthM, 0))}
            </p>
          </div>
          <ChevronRight className="self-center text-muted-foreground" />
        </button>
      ))}
      {!jobs.length && (
        <Empty text="No jobs received from PrusaSlicer." />
      )}
    </div>
  );
}
function SettingsView({
  user,
  printers,
  spools,
  onUserUpdated,
  onLogout,
}: {
  user: User;
  printers: Printer[];
  spools: Spool[];
  onUserUpdated: (user: User) => void;
  onLogout: () => void;
}) {
  const [message, setMessage] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [token, setToken] = useState('');
  const [tokenPrinterId, setTokenPrinterId] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [userDialog, setUserDialog] = useState(false);
  const [userError, setUserError] = useState('');
  const [userMessage, setUserMessage] = useState('');
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [passwordError, setPasswordError] = useState('');
  const [passwordMessage, setPasswordMessage] = useState('');
  const loadUsers = useCallback(async () => {
    if (user.role !== 'admin') return;
    try {
      setUsers(await api<User[]>('/api/users'));
      setUserError('');
    } catch (reason) {
      setUserError(
        reason instanceof Error ? reason.message : 'Could not load users',
      );
    }
  }, [user.role]);
  useEffect(() => {
    if (user.role !== 'admin') return;
    let current = true;
    api<User[]>('/api/users')
      .then((rows) => {
        if (current) setUsers(rows);
      })
      .catch((reason) => {
        if (current)
          setUserError(
            reason instanceof Error ? reason.message : 'Could not load users',
          );
      });
    return () => {
      current = false;
    };
  }, [user.role]);
  async function sync() {
    setSyncing(true);
    setMessage('');
    try {
      const result = await api<{ count: number }>('/api/catalog/sync', {
        method: 'POST',
      });
      setMessage(
        `${result.count.toLocaleString('en-US')} catalog records synchronized.`,
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Synchronization failed');
    } finally {
      setSyncing(false);
    }
  }
  async function createToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const printerId = form.get('printerId');
    if (typeof printerId !== 'string' || !printerId) return;
    const result = await api<{ token: string }>('/api/tokens', {
      method: 'POST',
      body: JSON.stringify({
        name: form.get('name'),
        printer_id: printerId,
      }),
    });
    setToken(result.token);
    setTokenPrinterId(printerId);
  }
  async function setUserActive(account: User, active: boolean) {
    try {
      await api(`/api/users/${account.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ active }),
      });
      await loadUsers();
    } catch (reason) {
      setUserError(reason instanceof Error ? reason.message : 'Update failed');
    }
  }
  async function updatePreferredUnit(preferredUnit: User['preferredUnit']) {
    try {
      const updated = await api<User>('/api/account/preferences', {
        method: 'PUT', body: JSON.stringify({ preferred_unit: preferredUnit }),
      });
      onUserUpdated(updated);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Preference update failed');
    }
  }
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const next = formText(form, 'newPassword');
    setPasswordError(''); setPasswordMessage('');
    if (next !== formText(form, 'confirmPassword')) { setPasswordError('New passwords do not match'); return; }
    try {
      const updated = await api<User>('/api/account/password', { method: 'PUT', body: JSON.stringify({ current_password: formText(form, 'currentPassword'), new_password: next }) });
      onUserUpdated(updated); setPasswordMessage('Password changed.'); formElement.reset();
    } catch (reason) { setPasswordError(reason instanceof Error ? reason.message : 'Password change failed'); }
  }
  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resetUser) return;
    const form = new FormData(event.currentTarget);
    const temporary = formText(form, 'temporaryPassword');
    setUserError(''); setUserMessage('');
    if (temporary !== formText(form, 'confirmTemporaryPassword')) { setUserError('Temporary passwords do not match'); return; }
    try {
      const displayName = resetUser.displayName;
      await api(`/api/users/${resetUser.id}/password`, { method: 'PUT', body: JSON.stringify({ temporary_password: temporary }) });
      setResetUser(null); setUserMessage(`Temporary password set for ${displayName}.`); await loadUsers();
    } catch (reason) { setUserError(reason instanceof Error ? reason.message : 'Password reset failed'); }
  }
  const configureCommand =
    token && tokenPrinterId
      ? `python filaflow_hook.py --add-printer "${typeof window === 'undefined' ? '' : window.location.origin}" "${tokenPrinterId}" "${token}" "${printers.find((printer) => printer.id === tokenPrinterId)?.slicerProfile ?? ''}"`
      : '';
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="rounded-2xl border bg-card p-5">
        <h2 className="font-bold">Account</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {user.displayName} · {user.email} · {user.role}
        </p>
        <div className="mt-5 max-w-xs space-y-2"><Label htmlFor="preferred-unit">Inventory units</Label><select id="preferred-unit" className="h-10 w-full rounded-lg border bg-background px-3 text-sm" value={user.preferredUnit} onChange={(event) => void updatePreferredUnit(event.target.value as User['preferredUnit'])}><option value="grams">Grams</option><option value="meters">Meters</option><option value="both">Both</option></select></div>
        <form className="mt-6 max-w-md space-y-3 border-t pt-5" onSubmit={changePassword}>
          <h3 className="text-sm font-semibold">Change password</h3>
          <PasswordField label="Current password" name="currentPassword" autoComplete="current-password" required />
          <PasswordField label="New password" name="newPassword" minLength={12} autoComplete="new-password" required />
          <PasswordField label="Confirm new password" name="confirmPassword" minLength={12} autoComplete="new-password" required />
          {passwordError && <p className="text-sm text-destructive">{passwordError}</p>}
          {passwordMessage && <p className="text-sm text-emerald-600">{passwordMessage}</p>}
          <Button type="submit" variant="outline">Change password</Button>
        </form>
        <Button variant="outline" className="mt-5" onClick={onLogout}>
          <LogOut className="size-4" /> Sign out
        </Button>
      </section>
      {user.role === 'admin' && (
        <section className="rounded-2xl border bg-card p-5 lg:col-span-2">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Users className="size-4 text-primary" />
                <h2 className="font-bold">Users</h2>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                Operators can manage filament and jobs. Administrators can also
                manage users, tokens and catalog synchronization.
              </p>
            </div>
            <Button onClick={() => setUserDialog(true)}>
              <UserPlus className="size-4" /> Add user
            </Button>
          </div>
          <div className="mt-5 divide-y rounded-xl border">
            {users.map((account) => (
              <div
                key={account.id}
                className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold">
                      {account.displayName}
                    </p>
                    <Badge variant={account.active ? 'secondary' : 'outline'}>
                      {account.active ? 'Active' : 'Inactive'}
                    </Badge>
                    <Badge variant="outline">{account.role}</Badge>
                    {account.mustChangePassword && <Badge variant="outline">Password change required</Badge>}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {account.email}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={account.id === user.id}
                  onClick={() => { setUserError(''); setUserMessage(''); setResetUser(account); }}
                >
                  Reset password
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={account.id === user.id}
                  onClick={() => setUserActive(account, !account.active)}
                >
                  {account.active ? 'Deactivate' : 'Activate'}
                </Button>
              </div>
            ))}
            {!users.length && (
              <p className="px-4 py-6 text-sm text-muted-foreground">
                No users found.
              </p>
            )}
          </div>
          {userError && (
            <p className="mt-3 text-sm text-destructive">{userError}</p>
          )}
          {userMessage && <p className="mt-3 text-sm text-emerald-600">{userMessage}</p>}
        </section>
      )}
      {user.role === 'admin' && (
        <>
          <InventorySettingsPanel />
          <section className="rounded-2xl border bg-card p-5">
            <h2 className="font-bold">OpenPrintTag</h2>
            <Button className="mt-5" onClick={sync} disabled={syncing}>
              <CloudDownload
                className={`size-4 ${syncing ? 'animate-pulse' : ''}`}
              />{' '}
              Synchronize
            </Button>
            {message && <p className="mt-3 text-sm">{message}</p>}
          </section>
          <section className="rounded-2xl border bg-card p-5">
            <h2 className="font-bold">PrusaSlicer API token</h2>
            <form className="mt-4 space-y-3" onSubmit={createToken}>
              <Field
                label="Token name"
                name="name"
                placeholder="Studio workstation"
                required
              />
              <div>
                <Label htmlFor="printerId">Printer</Label>
                <select
                  id="printerId"
                  name="printerId"
                  required
                  className="mt-2 h-10 w-full rounded-lg border bg-background px-3 text-sm"
                >
                  <option value="">Select a printer</option>
                  {printers.map((printer) => (
                    <option key={printer.id} value={printer.id}>
                      {printer.code} · {printer.name}
                    </option>
                  ))}
                </select>
              </div>
              <Button type="submit">Generate token</Button>
            </form>
            {token && (
              <div className="mt-4 rounded-xl bg-muted p-3">
                <p className="text-xs font-semibold text-orange-600">
                  Copy this token now. It will not be shown again.
                </p>
                <code className="mt-2 block break-all text-xs">{token}</code>
                <p className="mt-4 text-xs font-semibold">Configure client</p>
                <code className="mt-2 block break-all text-xs">
                  {configureCommand}
                </code>
                <p className="mt-3 text-xs text-muted-foreground">Run one generated command for every printer. The first configured printer becomes the default.</p>
              </div>
            )}
          </section>
        </>
      )}
      <section className="rounded-2xl border bg-card p-5">
        <h2 className="font-bold">Data export</h2>
        <div className="mt-5 flex gap-2">
          <Button
            variant="outline"
            onClick={() => (location.href = '/api/export/spools.csv')}
          >
            <Download className="size-4" /> CSV
          </Button>
          <Button
            variant="outline"
            onClick={() => (location.href = '/api/export/backup.json')}
          >
            <Database className="size-4" /> JSON
          </Button>
        </div>
      </section>
      <LabelTemplatesPanel user={user} spools={spools} />
      <AddUserDialog
        open={userDialog}
        onOpenChange={setUserDialog}
        onCreated={loadUsers}
      />
      <Dialog open={Boolean(resetUser)} onOpenChange={(open) => { if (!open) setResetUser(null); }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Reset password</DialogTitle><DialogDescription>Set a temporary password for {resetUser?.displayName}. Existing browser sessions will be signed out.</DialogDescription></DialogHeader>
          <form key={resetUser?.id} className="space-y-4" onSubmit={resetPassword}>
            <PasswordField label="Temporary password" name="temporaryPassword" minLength={12} autoComplete="new-password" required />
            <PasswordField label="Confirm temporary password" name="confirmTemporaryPassword" minLength={12} autoComplete="new-password" required />
            <DialogFooter><Button type="button" variant="outline" onClick={() => setResetUser(null)}>Cancel</Button><Button type="submit">Reset password</Button></DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InventorySettingsPanel() {
  const [payload, setPayload] = useState<ReorderPayload | null>(null);
  const [threshold, setThreshold] = useState('500');
  const [error, setError] = useState('');
  const load = useCallback(() => api<ReorderPayload>('/api/inventory/reorder-suggestions?all=true').then((row) => { setPayload(row); setThreshold(String(row.defaultThresholdG)); }).catch((reason) => setError(reason instanceof Error ? reason.message : 'Could not load reorder settings')), []);
  useEffect(() => { void load(); }, [load]);
  async function saveGlobal() {
    try { await api('/api/inventory/settings', { method: 'PUT', body: JSON.stringify({ reorder_threshold_g: Number(threshold) }) }); await load(); setError(''); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save threshold'); }
  }
  async function saveRule(group: ReorderGroup, ignored: boolean, custom?: number | null) {
    try {
      await api('/api/inventory/reorder-rules', { method: 'PUT', body: JSON.stringify({ product_key: group.productKey, threshold_g: custom, ignored, product_snapshot: { brand: group.brand, materialName: group.materialName, materialType: group.materialType, colorHex: group.colorHex, diameterMm: group.diameterMm } }) });
      await load(); setError('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save reorder rule'); }
  }
  return <section className="rounded-2xl border bg-card p-5 lg:col-span-2">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="font-bold">Reorder suggestions</h2><p className="mt-1 text-sm text-muted-foreground">Suggestions use available stock: remaining minus soft reservations.</p></div><div className="flex items-end gap-2"><div><Label htmlFor="global-threshold">Default threshold (g)</Label><Input id="global-threshold" className="mt-2 w-36" type="number" min="0" value={threshold} onChange={(event) => setThreshold(event.target.value)} /></div><Button onClick={saveGlobal}>Save</Button></div></div>
    {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
    <div className="mt-5 grid gap-2 md:grid-cols-2">{payload?.groups.slice(0, 12).map((group) => <div key={group.productKey} className="flex items-center gap-3 rounded-xl border p-3"><span className="size-8 rounded-lg border" style={{ background: group.colorHex }} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{group.brand} · {group.materialName}</p><p className="text-xs text-muted-foreground">{formatWeight(group.availableWeightG)} available · threshold {formatWeight(group.thresholdG)}</p></div><Button size="sm" variant="ghost" onClick={() => { const answer = prompt('Custom threshold in grams. Leave empty to use the default.', String(group.thresholdG)); if (answer !== null) void saveRule(group, false, answer.trim() ? Number(answer) : null); }}>Threshold</Button><Button size="sm" variant="ghost" onClick={() => void saveRule(group, !group.ignored, group.thresholdG === payload.defaultThresholdG ? null : group.thresholdG)}>{group.ignored ? 'Enable' : 'Ignore'}</Button></div>)}</div>
  </section>;
}

const LABEL_ELEMENT_NAMES: Record<string, string> = {
  qr: 'QR code', code: 'SPL code', serial: 'Spool serial number', brand: 'Brand', filament: 'Filament name', material: 'Material',
  color_swatch: 'Color swatch', color_name: 'Color name', color_hex: 'Hex code', location: 'Location', remaining: 'Remaining', custom_text: 'Static text', border: 'Border',
};

function LabelTemplatesPanel({ user, spools }: { user: User; spools: Spool[] }) {
  const [templates, setTemplates] = useState<LabelTemplate[]>([]);
  const [editing, setEditing] = useState<LabelTemplate | null>(null);
  const [error, setError] = useState('');
  const load = useCallback(() => api<LabelTemplate[]>('/api/label-templates').then(setTemplates).catch((reason) => setError(reason instanceof Error ? reason.message : 'Could not load label templates')), []);
  useEffect(() => { void load(); }, [load]);
  async function duplicate(template: LabelTemplate) {
    try { const copy = await api<LabelTemplate>(`/api/label-templates/${template.id}/duplicate`, { method: 'POST' }); await load(); setEditing(copy); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not duplicate template'); }
  }
  async function makeDefault(template: LabelTemplate) { try { await api(`/api/label-templates/${template.id}/default`, { method: 'POST' }); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not change the default'); } }
  async function archive(template: LabelTemplate) { try { await api(`/api/label-templates/${template.id}/archive`, { method: 'POST' }); await load(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not archive template'); } }
  const previewSpool = spools[0];
  return <section className="rounded-2xl border bg-card p-5 lg:col-span-2">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h2 className="font-bold">Label templates</h2><p className="mt-1 text-sm text-muted-foreground">Built-in presets are protected. Duplicate one to create an editable template.</p></div>{user.role === 'admin' && templates[0] && <Button onClick={() => void duplicate(templates.find((row) => row.isDefault) ?? templates[0])}><Plus className="size-4" /> New from default</Button>}</div>
    {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
    <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{templates.map((template) => <article key={template.id} className="rounded-xl border p-4"><div className="flex items-start justify-between gap-2"><div><p className="font-semibold">{template.name}</p><p className="text-xs text-muted-foreground">{template.widthMm} × {template.heightMm} mm</p></div><div className="flex gap-1">{template.builtin && <Badge variant="outline">Preset</Badge>}{template.isDefault && <Badge>Default</Badge>}</div></div>{previewSpool && <div className="mt-4 grid h-28 place-items-center overflow-hidden rounded-lg bg-muted p-2"><img src={`/api/spools/${previewSpool.id}/label.svg?templateId=${template.id}`} alt={`Preview of ${template.name}`} className="max-h-full max-w-full shadow" /></div>}<div className="mt-4 flex flex-wrap gap-2">{user.role === 'admin' && <Button size="sm" variant="outline" onClick={() => template.builtin ? void duplicate(template) : setEditing(template)}>{template.builtin ? <Copy className="size-4" /> : <Pencil className="size-4" />}{template.builtin ? 'Duplicate' : 'Edit'}</Button>}{!template.isDefault && user.role === 'admin' && <Button size="sm" variant="ghost" onClick={() => void makeDefault(template)}>Set default</Button>}{!template.builtin && user.role === 'admin' && <Button size="sm" variant="ghost" className="text-destructive" onClick={() => void archive(template)}>Archive</Button>}{previewSpool && <Button size="sm" variant="ghost" onClick={() => window.open(`/labels/print?spools=${previewSpool.id}&template=${template.id}`, '_blank')}>Print test</Button>}</div></article>)}</div>
    {editing && <LabelEditorDialog template={editing} open onOpenChange={(open) => !open && setEditing(null)} onSaved={async () => { setEditing(null); await load(); }} />}
  </section>;
}

function LabelEditorDialog({ template, open, onOpenChange, onSaved }: { template: LabelTemplate; open: boolean; onOpenChange: (open: boolean) => void; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(template.name);
  const [width, setWidth] = useState(template.widthMm);
  const [height, setHeight] = useState(template.heightMm);
  const [layout, setLayout] = useState<LabelElement[]>(template.layout.map((row) => ({ ...row })));
  const [selectedId, setSelectedId] = useState(template.layout[0]?.id ?? '');
  const [history, setHistory] = useState<LabelElement[][]>([]);
  const [future, setFuture] = useState<LabelElement[][]>([]);
  const [monochrome, setMonochrome] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [error, setError] = useState('');
  const canvasRef = useRef<HTMLDivElement>(null);
  const gestureRef = useRef<{
    id: string;
    mode: 'move' | 'resize';
    pointerId: number;
    startClientX: number;
    startClientY: number;
    rect: DOMRect;
    element: LabelElement;
    originalLayout: LabelElement[];
    changed: boolean;
  } | null>(null);
  const selected = layout.find((row) => row.id === selectedId);
  function commit(next: LabelElement[]) { setHistory((rows) => [...rows.slice(-39), layout]); setLayout(next); setFuture([]); }
  const snap = (value: number) => Math.round(value * 2) / 2;
  function constrain(element: LabelElement): LabelElement {
    const minimum = element.type === 'qr' ? 16 : 1;
    const next = { ...element };
    next.width = Math.max(minimum, Math.min(width, Number.isFinite(next.width) ? next.width : minimum));
    next.height = Math.max(minimum, Math.min(height, Number.isFinite(next.height) ? next.height : minimum));
    if (next.type === 'qr') {
      const size = Math.max(16, Math.min(width, height, Math.max(next.width, next.height)));
      next.width = size;
      next.height = size;
    }
    next.x = Math.max(0, Math.min(width - next.width, Number.isFinite(next.x) ? next.x : 0));
    next.y = Math.max(0, Math.min(height - next.height, Number.isFinite(next.y) ? next.y : 0));
    return next;
  }
  function patchSelected(changes: Partial<LabelElement>) {
    if (!selected) return;
    const adjusted = { ...selected, ...changes };
    if (selected.type === 'qr' && ('width' in changes || 'height' in changes)) {
      const size = Number(changes.width ?? changes.height ?? selected.width);
      adjusted.width = size;
      adjusted.height = size;
    }
    commit(layout.map((row) => row.id === selected.id ? constrain(adjusted) : row));
  }
  function undo() { const previous = history.at(-1); if (!previous) return; setFuture((rows) => [layout, ...rows]); setLayout(previous); setHistory((rows) => rows.slice(0, -1)); }
  function redo() { const next = future[0]; if (!next) return; setHistory((rows) => [...rows, layout]); setLayout(next); setFuture((rows) => rows.slice(1)); }
  function addElement(type: string) { const isQr = type === 'qr'; const element: LabelElement = { id: `${type}-${Date.now()}`, type, x: 2, y: 2, width: isQr ? 16 : Math.min(30, width - 4), height: isQr ? 16 : 5, font_size: 3, visible: true, text: type === 'custom_text' ? 'Custom text' : '', bold: false }; commit([...layout, element]); setSelectedId(element.id); }
  function moveLayer(direction: -1 | 1) { if (!selected) return; const index = layout.findIndex((row) => row.id === selected.id); const nextIndex = Math.max(0, Math.min(layout.length - 1, index + direction)); const next = [...layout]; next.splice(index, 1); next.splice(nextIndex, 0, selected); commit(next); }
  function alignSelected(mode: 'left' | 'horizontal' | 'vertical') {
    if (!selected) return;
    const changes = mode === 'left' ? { x: 0 } : mode === 'horizontal' ? { x: snap((width - selected.width) / 2) } : { y: snap((height - selected.height) / 2) };
    patchSelected(changes);
  }
  function fitElements() { commit(layout.map((row) => constrain(row))); }
  function beginGesture(event: ReactPointerEvent<HTMLElement>, element: LabelElement, mode: 'move' | 'resize') {
    if (event.button !== 0 || !canvasRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(element.id);
    gestureRef.current = {
      id: element.id, mode, pointerId: event.pointerId,
      startClientX: event.clientX, startClientY: event.clientY,
      rect: canvasRef.current.getBoundingClientRect(), element: { ...element },
      originalLayout: layout.map((row) => ({ ...row })), changed: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function continueGesture(event: ReactPointerEvent<HTMLElement>) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    const dx = (event.clientX - gesture.startClientX) / gesture.rect.width * width;
    const dy = (event.clientY - gesture.startClientY) / gesture.rect.height * height;
    let updated = { ...gesture.element };
    if (gesture.mode === 'move') {
      updated.x = snap(gesture.element.x + dx);
      updated.y = snap(gesture.element.y + dy);
    } else if (gesture.element.type === 'qr') {
      const size = snap(Math.max(16, gesture.element.width + Math.max(dx, dy)));
      updated.width = size;
      updated.height = size;
    } else {
      updated.width = snap(Math.max(1, gesture.element.width + dx));
      updated.height = snap(Math.max(1, gesture.element.height + dy));
    }
    updated = constrain(updated);
    gesture.changed = true;
    setLayout(gesture.originalLayout.map((row) => row.id === gesture.id ? updated : row));
  }
  function endGesture(event: ReactPointerEvent<HTMLElement>) {
    const gesture = gestureRef.current;
    if (!gesture || gesture.pointerId !== event.pointerId) return;
    if (gesture.changed) {
      setHistory((rows) => [...rows.slice(-39), gesture.originalLayout]);
      setFuture([]);
    }
    gestureRef.current = null;
  }
  function nudgeElement(event: ReactKeyboardEvent<HTMLElement>, element: LabelElement) {
    const delta = event.shiftKey ? 2 : 0.5;
    const directions: Record<string, Partial<LabelElement>> = {
      ArrowLeft: { x: element.x - delta }, ArrowRight: { x: element.x + delta },
      ArrowUp: { y: element.y - delta }, ArrowDown: { y: element.y + delta },
    };
    if (!directions[event.key]) return;
    event.preventDefault();
    setSelectedId(element.id);
    commit(layout.map((row) => row.id === element.id ? constrain({ ...element, ...directions[event.key] }) : row));
  }
  function resizeElement(event: ReactKeyboardEvent<HTMLElement>, element: LabelElement) {
    const delta = event.shiftKey ? 2 : 0.5;
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
    const grow = event.key === 'ArrowRight' || event.key === 'ArrowDown' ? delta : -delta;
    const updated = element.type === 'qr'
      ? { ...element, width: element.width + grow, height: element.height + grow }
      : event.key === 'ArrowLeft' || event.key === 'ArrowRight'
        ? { ...element, width: element.width + grow }
        : { ...element, height: element.height + grow };
    commit(layout.map((row) => row.id === element.id ? constrain(updated) : row));
  }
  async function save() { try { setError(''); await api(`/api/label-templates/${template.id}`, { method: 'PUT', body: JSON.stringify({ name, width_mm: width, height_mm: height, layout }) }); await onSaved(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save template'); } }
  const sample: Record<string, string> = { qr: 'QR', code: 'SPL-0127', serial: 'Spool S/N: SN-0042', brand: 'Prusament', filament: 'Galaxy Black', material: 'PETG', color_name: 'Black', color_hex: '#111827', location: 'Shelf A', remaining: '742 g · 247 m', custom_text: selected?.text || 'Custom text', border: '' };
  const overflows = layout.filter((row) => row.x < 0 || row.y < 0 || row.x + row.width > width || row.y + row.height > height || (row.type === 'qr' && (row.width < 16 || row.height < 16 || Math.abs(row.width - row.height) > .1)));
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-h-[94vh] overflow-y-auto sm:max-w-7xl"><DialogHeader><DialogTitle>Label editor</DialogTitle><DialogDescription>The canvas uses real CSS millimetres at 100%. Drag from where you grab an element; use the blue handle to resize.</DialogDescription></DialogHeader>
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_330px]"><div><div className="mb-3 flex flex-wrap items-center gap-2"><Button size="sm" variant="outline" disabled={!history.length} onClick={undo}><RotateCcw className="size-4" /> Undo</Button><Button size="sm" variant="outline" disabled={!future.length} onClick={redo}>Redo</Button><Button size="sm" variant={monochrome ? 'secondary' : 'outline'} onClick={() => setMonochrome((value) => !value)}><Eye className="size-4" /> Monochrome</Button><select aria-label="Editor zoom" className="h-9 rounded-lg border bg-background px-2 text-sm" value={zoom} onChange={(event) => setZoom(Number(event.target.value))}><option value="0.75">75%</option><option value="1">100% · actual size</option><option value="1.5">150%</option><option value="2">200%</option></select><select className="h-9 rounded-lg border bg-background px-2 text-sm" defaultValue="" onChange={(event) => { if (event.target.value) addElement(event.target.value); event.target.value = ''; }}><option value="">Add element…</option>{Object.entries(LABEL_ELEMENT_NAMES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><span className="ml-auto text-xs text-muted-foreground">Print size: {width} × {height} mm</span></div>
      <div className="min-h-72 overflow-auto rounded-2xl bg-muted p-8"><div ref={canvasRef} role="listbox" tabIndex={0} aria-label={`${width} by ${height} millimetre label canvas`} className="relative mx-auto overflow-hidden bg-white shadow-xl" onPointerMove={continueGesture} onPointerUp={endGesture} onPointerCancel={endGesture} onClick={() => setSelectedId('')} onKeyDown={(event) => { if (event.key === 'Escape') setSelectedId(''); }} style={{ width: `${width * zoom}mm`, height: `${height * zoom}mm`, backgroundImage: 'linear-gradient(#d1d5db55 1px, transparent 1px), linear-gradient(90deg, #d1d5db55 1px, transparent 1px)', backgroundSize: `${zoom}mm ${zoom}mm` }}>
        {selected && Math.abs(selected.x + selected.width / 2 - width / 2) <= .5 && <span className="pointer-events-none absolute inset-y-0 left-1/2 z-20 border-l border-dashed border-blue-500" />}
        {selected && Math.abs(selected.y + selected.height / 2 - height / 2) <= .5 && <span className="pointer-events-none absolute inset-x-0 top-1/2 z-20 border-t border-dashed border-blue-500" />}
        {layout.map((element) => element.visible && <div role="option" aria-selected={selectedId === element.id} tabIndex={0} key={element.id} aria-label={`Edit ${LABEL_ELEMENT_NAMES[element.type] ?? element.type}`} onPointerDown={(event) => beginGesture(event, element, 'move')} onKeyDown={(event) => nudgeElement(event, element)} onClick={(event) => { event.stopPropagation(); setSelectedId(element.id); }} className={`absolute flex cursor-move touch-none select-none items-center overflow-hidden text-left leading-none ${selectedId === element.id ? 'z-10 ring-2 ring-blue-500' : 'hover:ring-1 hover:ring-blue-300'} ${element.type === 'border' ? 'border border-gray-900' : ''}`} style={{ left: `${element.x / width * 100}%`, top: `${element.y / height * 100}%`, width: `${element.width / width * 100}%`, height: `${element.height / height * 100}%`, fontSize: `${Math.max(1.5, element.font_size) * zoom}mm`, fontWeight: element.bold ? 700 : 400, color: '#111827', background: element.type === 'color_swatch' ? (monochrome ? '#fff' : '#111827') : element.type === 'qr' ? `repeating-conic-gradient(#111 0 25%, #fff 0 50%) 0 / ${2 * zoom}mm ${2 * zoom}mm` : undefined }}>{element.type !== 'qr' && element.type !== 'color_swatch' && element.type !== 'border' ? (element.type === 'custom_text' ? element.text : sample[element.type]) : null}{selectedId === element.id && <span aria-label={`Resize ${LABEL_ELEMENT_NAMES[element.type] ?? element.type}`} role="slider" aria-valuemin={element.type === 'qr' ? 16 : 1} aria-valuemax={Math.min(width - element.x, height - element.y)} aria-valuenow={element.width} tabIndex={0} onPointerDown={(event) => beginGesture(event, element, 'resize')} onKeyDown={(event) => resizeElement(event, element)} className="absolute bottom-0 right-0 size-3 cursor-nwse-resize touch-none rounded-tl bg-blue-600 ring-1 ring-white" />}</div>)}
      </div></div>{overflows.length > 0 && <p className="mt-3 rounded-xl bg-orange-500/10 p-3 text-sm text-orange-700">{overflows.length} element(s) violate the label boundary or QR minimum size.</p>}</div>
      <aside className="space-y-4"><div className="grid grid-cols-2 gap-3"><Field label="Template name" name="labelName" value={name} onChange={(event) => setName(event.target.value)} className="col-span-2" /><Field label="Width (mm)" name="labelWidth" type="number" min="20" max="200" step="0.5" value={width} onChange={(event) => { const value = Number(event.target.value); if (Number.isFinite(value)) setWidth(Math.max(20, Math.min(200, value))); }} /><Field label="Height (mm)" name="labelHeight" type="number" min="15" max="150" step="0.5" value={height} onChange={(event) => { const value = Number(event.target.value); if (Number.isFinite(value)) setHeight(Math.max(15, Math.min(150, value))); }} /><Button size="sm" variant="outline" className="col-span-2" onClick={fitElements}>Keep all elements inside label</Button></div>
      <div><Label htmlFor="selected-label-element" className="text-[11px]">Selected element</Label><select id="selected-label-element" className="mt-1 h-9 w-full rounded-lg border bg-background px-2 text-sm" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}><option value="">None</option>{layout.map((row) => <option key={row.id} value={row.id}>{LABEL_ELEMENT_NAMES[row.type] ?? row.type}</option>)}</select></div>
      {selected ? <div className="space-y-3 rounded-xl border p-4"><div className="flex items-center justify-between"><p className="font-semibold">{LABEL_ELEMENT_NAMES[selected.type] ?? selected.type}</p><label className="flex items-center gap-2 text-xs"><input aria-label="Show element" type="checkbox" checked={selected.visible} onChange={(event) => patchSelected({ visible: event.target.checked })} /> Visible</label></div><p className="text-xs text-muted-foreground">Drag to move, use the blue corner to resize, or press arrow keys. Hold Shift for 2 mm steps.</p><div className="grid grid-cols-2 gap-2">{(['x','y','width','height'] as const).map((key) => <div key={key}><Label className="text-[11px]">{key.toUpperCase()} (mm)</Label><Input type="number" step="0.5" min="0" value={selected[key]} onChange={(event) => patchSelected({ [key]: Number(event.target.value) })} /></div>)}</div><div className="grid grid-cols-3 gap-1"><Button size="sm" variant="outline" onClick={() => alignSelected('left')}>Left</Button><Button size="sm" variant="outline" onClick={() => alignSelected('horizontal')}>Center X</Button><Button size="sm" variant="outline" onClick={() => alignSelected('vertical')}>Center Y</Button></div>{!['qr','color_swatch','border'].includes(selected.type) && <><div><Label className="text-[11px]">Font size (mm)</Label><Input type="number" min="1.5" max="20" step="0.1" value={selected.font_size} onChange={(event) => patchSelected({ font_size: Number(event.target.value) })} /></div>{selected.type === 'custom_text' && <div><Label className="text-[11px]">Text</Label><Input value={selected.text} onChange={(event) => patchSelected({ text: event.target.value })} /></div>}<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected.bold} onChange={(event) => patchSelected({ bold: event.target.checked })} /> Bold</label></>}<div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => moveLayer(-1)}>Send back</Button><Button size="sm" variant="outline" onClick={() => moveLayer(1)}>Bring forward</Button></div><Button size="sm" variant="ghost" className="text-destructive" onClick={() => { commit(layout.filter((row) => row.id !== selected.id)); setSelectedId(''); }}>Remove element</Button></div> : <p className="text-sm text-muted-foreground">Select an element on the canvas or from the list.</p>}
      </aside></div>{error && <p className="text-sm text-destructive">{error}</p>}<DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={overflows.length > 0 || !name.trim()} onClick={() => void save()}><Save className="size-4" /> Save template</Button></DialogFooter>
  </DialogContent></Dialog>;
}

function LabelPrintView({ spools }: { spools: Spool[] }) {
  const ids = useMemo(() => new URLSearchParams(window.location.search).get('spools')?.split(',').filter(Boolean) ?? [], []);
  const [rows, setRows] = useState<Spool[]>(() => spools.filter((row) => ids.includes(row.id)));
  const [templates, setTemplates] = useState<LabelTemplate[]>([]);
  const [templateId, setTemplateId] = useState(() => new URLSearchParams(window.location.search).get('template') ?? '');
  const [monochrome, setMonochrome] = useState(false);
  const [loadedLabelIds, setLoadedLabelIds] = useState<Set<string>>(new Set());
  const [imageError, setImageError] = useState('');
  const [savingImages, setSavingImages] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  useEffect(() => {
    api<LabelTemplate[]>('/api/label-templates').then((items) => { setTemplates(items); setTemplateId((current) => current || items.find((item) => item.isDefault)?.id || items[0]?.id || ''); }).catch(() => undefined);
  }, []);
  useEffect(() => {
    Promise.all(ids.map((id) => api<Spool>(`/api/spools/${id}`))).then(setRows).catch(() => undefined);
  }, [ids]);
  const template = templates.find((row) => row.id === templateId);
  const widthMm = template?.widthMm ?? 90;
  const heightMm = template?.heightMm ?? 32;
  const imageKey = (spoolId: string) => `${spoolId}:${templateId}:${monochrome}`;
  const readyToPrint = Boolean(template && rows.length && rows.every((spool) => loadedLabelIds.has(imageKey(spool.id))) && !imageError);
  async function saveImages() {
    if (!template || !readyToPrint) return;
    setSavingImages(true);
    setSaveMessage('');
    try {
      const isB1Pro50x30 = Math.abs(widthMm - 50) < 0.01 && Math.abs(heightMm - 30) < 0.01;
      const pixelWidth = isB1Pro50x30 ? 584 : Math.max(1, Math.round(widthMm / 25.4 * 300));
      const pixelHeight = isB1Pro50x30 ? 354 : Math.max(1, Math.round(heightMm / 25.4 * 300));
      for (const spool of rows) {
        const response = await fetch(`/api/spools/${spool.id}/label.svg?templateId=${templateId}&monochrome=${monochrome}`);
        if (!response.ok) throw new Error(`Label ${spool.code} could not be exported`);
        const svgUrl = URL.createObjectURL(await response.blob());
        try {
          const image = new Image();
          image.src = svgUrl;
          await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error(`Label ${spool.code} could not be rendered`)); });
          const canvas = document.createElement('canvas');
          canvas.width = pixelWidth;
          canvas.height = pixelHeight;
          const context = canvas.getContext('2d');
          if (!context) throw new Error('PNG export is unavailable in this browser');
          context.fillStyle = '#ffffff';
          context.fillRect(0, 0, pixelWidth, pixelHeight);
          context.drawImage(image, 0, 0, pixelWidth, pixelHeight);
          const png = await new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('PNG export failed')), 'image/png'));
          const pngUrl = URL.createObjectURL(png);
          const link = document.createElement('a');
          link.href = pngUrl;
          link.download = `${spool.code}-${widthMm}x${heightMm}mm.png`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => URL.revokeObjectURL(pngUrl), 1000);
        } finally {
          URL.revokeObjectURL(svgUrl);
        }
      }
      setSaveMessage(`${rows.length} PNG ${rows.length === 1 ? 'image' : 'images'} saved at ${pixelWidth} × ${pixelHeight} px.`);
    } catch (reason) {
      setSaveMessage(reason instanceof Error ? reason.message : 'PNG export failed');
    } finally {
      setSavingImages(false);
    }
  }
  return <main className="label-print-root min-h-screen bg-muted p-5 text-foreground"><style>{`@media print {
    @page { margin: 0; size: ${widthMm}mm ${heightMm}mm; }
    html, body, #root { width: ${widthMm}mm !important; margin: 0 !important; padding: 0 !important; background: white !important; }
    .label-print-root { width: ${widthMm}mm !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important; background: white !important; }
    .label-print-controls { display: none !important; }
    .label-print-sheet { display: block !important; width: ${widthMm}mm !important; max-width: none !important; margin: 0 !important; padding: 0 !important; border-radius: 0 !important; }
    .label-print-item { width: ${widthMm}mm !important; height: ${heightMm}mm !important; margin: 0 !important; overflow: hidden !important; break-inside: avoid; break-after: page; page-break-inside: avoid; page-break-after: always; box-shadow: none !important; }
    .label-print-item:last-child { break-after: auto; page-break-after: auto; }
    .label-print-item img { display: block !important; width: 100% !important; height: 100% !important; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  }`}</style><section className="label-print-controls mx-auto mb-5 flex max-w-4xl flex-wrap items-end gap-3 rounded-2xl border bg-card p-4"><div className="mr-auto"><h1 className="font-bold">Print labels</h1><p className="text-xs text-muted-foreground">Use 100% scale, zero margins, and disable browser headers and footers.</p>{!readyToPrint && rows.length > 0 && !imageError && <p className="mt-1 text-xs text-muted-foreground">Preparing label preview…</p>}{imageError && <p className="mt-1 text-xs text-destructive">{imageError}</p>}{saveMessage && <p className="mt-1 text-xs text-muted-foreground">{saveMessage}</p>}</div><div><Label htmlFor="print-template">Template</Label><select id="print-template" className="mt-1 h-9 rounded-lg border bg-background px-3 text-sm" value={templateId} onChange={(event) => { setImageError(''); setSaveMessage(''); setTemplateId(event.target.value); }}>{templates.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></div><label className="flex h-9 items-center gap-2 text-sm"><input type="checkbox" checked={monochrome} onChange={(event) => { setImageError(''); setSaveMessage(''); setMonochrome(event.target.checked); }} /> Monochrome</label><Button variant="outline" disabled={!readyToPrint || savingImages} onClick={() => void saveImages()}><Download className="size-4" /> {savingImages ? 'Saving…' : rows.length > 1 ? 'Save images' : 'Save image'}</Button><Button disabled={!readyToPrint} onClick={() => window.print()}><PrinterIcon className="size-4" /> Print</Button></section><section className="label-print-sheet mx-auto grid max-w-5xl gap-4 rounded-2xl bg-white p-5">{template && rows.map((spool) => <div key={spool.id} className="label-print-item overflow-hidden bg-white shadow" style={{ width: `${widthMm}mm`, height: `${heightMm}mm` }}><img key={imageKey(spool.id)} src={`/api/spools/${spool.id}/label.svg?templateId=${templateId}&monochrome=${monochrome}`} alt={`Label ${spool.code}`} className="block h-full w-full" onLoad={() => setLoadedLabelIds((current) => new Set(current).add(imageKey(spool.id)))} onError={() => setImageError(`Label ${spool.code} could not be loaded. Refresh this page and try again.`)} /></div>)}{!rows.length && <Empty text="No spools selected." />}</section></main>;
}

function DirectSpoolView({ spoolId, preference }: { spoolId: string; preference: User['preferredUnit'] }) {
  const [spool, setSpool] = useState<Spool | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { api<Spool>(`/api/spools/${spoolId}`).then(setSpool).catch((reason) => setError(reason instanceof Error ? reason.message : 'Spool not found')); }, [spoolId]);
  return <main className="min-h-screen bg-background p-5"><div className="mx-auto max-w-xl"><Button variant="outline" onClick={() => { window.location.href = '/'; }}><ChevronRight className="size-4 rotate-180" /> Back to FilaFlow</Button>{error && <p className="mt-5 text-sm text-destructive">{error}</p>}{!spool && !error && <div className="mt-5 h-48 animate-pulse rounded-2xl bg-muted" />}{spool && <SpoolDetailSheet spool={spool} open onOpenChange={(open) => { if (!open) window.location.href = '/'; }} preference={preference} />}</div></main>;
}

function AddUserDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => Promise<void>;
}) {
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      await api('/api/users', {
        method: 'POST',
        body: JSON.stringify({
          display_name: form.get('displayName'),
          email: form.get('email'),
          password: form.get('password'),
          role: form.get('role'),
        }),
      });
      onOpenChange(false);
      await onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not add user');
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add user</DialogTitle>
          <DialogDescription className="sr-only">
            Create a FilaFlow account.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <Field label="Display name" name="displayName" required />
          <Field label="Email address" name="email" type="email" required />
          <Field
            label="Temporary password"
            name="password"
            type="password"
            minLength={12}
            autoComplete="new-password"
            required
          />
          <div className="space-y-2">
            <Label htmlFor="userRole">Role</Label>
            <select
              id="userRole"
              name="role"
              defaultValue="operator"
              className="h-9 w-full rounded-lg border bg-background px-3 text-sm"
            >
              <option value="operator">Operator</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit">Create user</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  name,
  ...props
}: { label: string; name: string } & React.ComponentProps<typeof Input>) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} name={name} {...props} />
    </div>
  );
}

function PasswordField({ label, name, ...props }: { label: string; name: string } & Omit<React.ComponentProps<typeof Input>, 'type'>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <div className="relative">
        <Input id={name} name={name} type={visible ? 'text' : 'password'} className="pr-10" {...props} />
        <button type="button" className="absolute inset-y-0 right-0 grid w-10 place-items-center text-muted-foreground" onClick={() => setVisible((value) => !value)} aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}>
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
    </div>
  );
}

function LocationField({ defaultValue = '' }: { defaultValue?: string }) {
  const listId = useId();
  const [locations, setLocations] = useState<string[]>([]);
  useEffect(() => { api<string[]>('/api/locations').then(setLocations).catch(() => setLocations([])); }, []);
  return (
    <div className="space-y-2">
      <Label htmlFor={`${listId}-location`}>Location</Label>
      <Input id={`${listId}-location`} name="location" list={listId} defaultValue={defaultValue} />
      <datalist id={listId}>{locations.map((location) => <option aria-label={location} key={location} value={location} />)}</datalist>
    </div>
  );
}

function ColorInputs({ defaultName = '', defaultHex = '#808080' }: { defaultName?: string; defaultHex?: string }) {
  const [value, setValue] = useState(defaultHex);
  const [name, setName] = useState(defaultName);
  const [automatic, setAutomatic] = useState(!defaultName);
  useEffect(() => {
    if (!automatic || !/^#[0-9A-Fa-f]{6}$/.test(value)) return;
    const timer = setTimeout(() => {
      api<{ name: string }>(`/api/colors/nearest?hex=${encodeURIComponent(value)}`)
        .then((result) => setName(result.name))
        .catch(() => undefined);
    }, 180);
    return () => clearTimeout(timer);
  }, [automatic, value]);
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="colorName">Color name</Label>
        <Input id="colorName" name="colorName" value={name} onChange={(event) => { setName(event.target.value); setAutomatic(!event.target.value); }} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="colorHex">Color (HEX)</Label>
        <div className="flex gap-2">
        <Input
          aria-label="Color picker"
          type="color"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="w-14 shrink-0 px-1"
        />
        <Input
          id="colorHex"
          name="colorHex"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          pattern="#[0-9A-Fa-f]{6}"
          placeholder="#808080"
          required
        />
        </div>
      </div>
    </>
  );
}

function AddSpoolDialog({
  open,
  onOpenChange,
  onCreated,
  template,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => Promise<void>;
  template: Spool | null;
}) {
  const [query, setQuery] = useState('');
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [picked, setPicked] = useState<CatalogItem | null>(null);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim().length >= 2 && !picked) {
        setSearching(true);
        api<CatalogItem[]>(
          `/api/catalog/search?q=${encodeURIComponent(query)}&limit=60`,
        )
          .then((items) => {
            setCatalog(items);
            setSearched(true);
          })
          .catch(() => setCatalog([]))
          .finally(() => setSearching(false));
      } else if (query.trim().length < 2) {
        setCatalog([]);
        setSearched(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [picked, query]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const payload = {
      brand: f.get('brand'),
      material_name: f.get('materialName'),
      material_type: f.get('materialType'),
      color_name: f.get('colorName'),
      color_hex: f.get('colorHex'),
      location: f.get('location'),
      lot_number: f.get('lotNumber'),
      serial_number: f.get('serialNumber'),
      diameter_mm: Number(f.get('diameterMm')),
      density_g_cm3: Number(f.get('density')),
      tare_weight_g: Number(f.get('tareWeightG')),
      initial_weight_g: Number(f.get('initialWeightG')),
      initial_length_m: f.get('initialLengthM')
        ? Number(f.get('initialLengthM'))
        : null,
      low_stock_weight_g: Number(f.get('lowStockWeightG')),
      purchase_price: f.get('purchasePrice')
        ? Number(f.get('purchasePrice'))
        : null,
      currency: typeof f.get('currency') === 'string' ? (f.get('currency') as string).toUpperCase() : 'EUR',
      ...(picked
        ? {
            opt_brand_uuid: picked.opt.brandUuid,
            opt_material_uuid: picked.opt.materialUuid,
            opt_package_uuid: picked.opt.packageUuid,
            opt_container_uuid: picked.opt.containerUuid,
            catalog_snapshot: picked.raw,
          }
        : template
          ? {
              opt_brand_uuid: template.openPrintTag.brandUuid,
              opt_material_uuid: template.openPrintTag.materialUuid,
              opt_package_uuid: template.openPrintTag.packageUuid,
              opt_container_uuid: template.openPrintTag.containerUuid,
              catalog_snapshot: template.catalogSnapshot,
            }
          : {}),
    };
    try {
      await api('/api/spools', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      onOpenChange(false);
      setPicked(null);
      await onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Save failed');
    }
  }
  // oxlint-disable-next-line jsx-a11y/control-has-associated-label -- Catalog search has an adjacent visible label.
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add spool</DialogTitle>
          <DialogDescription className="sr-only">
            Add a spool from OpenPrintTag or manually.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="catalog-search">Search OpenPrintTag</Label>
          <Input
            id="catalog-search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPicked(null);
            }}
            placeholder="Brand, material, color, tag or GTIN"
          />
          {searching && (
            <p className="text-xs text-muted-foreground">Searching…</p>
          )}
          {catalog.length > 0 && !picked && (
            <div className="max-h-64 overflow-auto rounded-xl border p-1">
              {catalog.map((item) => (
                <button
                  key={item.id}
                  aria-label={`Select ${item.brand} ${item.materialName}`}
                  onClick={() => {
                    setPicked(item);
                    setQuery(`${item.brand} ${item.materialName}`);
                    setCatalog([]);
                  }}
                  className="flex w-full items-center gap-3 rounded-lg p-2 text-left hover:bg-muted"
                >
                  <span
                    className="size-7 rounded-lg"
                    style={{ background: item.colorHex }}
                  />
                  <div>
                    <p className="text-sm font-semibold">
                      {item.brand} · {item.materialName}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {item.materialType} · {item.nominalWeightG ?? '?'} g ·{' '}
                      {item.colorHex.toUpperCase()}
                      {item.gtin ? ` · GTIN ${item.gtin}` : ''}
                    </p>
                    {(item.containerName || item.packageName) && (
                      <p className="truncate text-xs text-muted-foreground/80">
                        {item.containerName ||
                          item.packageName.replaceAll('-', ' ')}
                      </p>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
          {!searching && searched && catalog.length === 0 && !picked && (
            <p className="text-xs text-muted-foreground">
              No matching OpenPrintTag material found. Try fewer words or enter
              the spool manually.
            </p>
          )}
          {picked && (
            <div className="flex items-center justify-between rounded-xl border bg-muted/40 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className="size-6 shrink-0 rounded-md border"
                  style={{ background: picked.colorHex }}
                />
                <p className="truncate text-sm font-semibold">
                  {picked.brand} · {picked.materialName}
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  setPicked(null);
                  setQuery('');
                }}
              >
                Clear
              </Button>
            </div>
          )}
        </div>
        <form
          key={picked?.id ?? template?.id ?? 'manual'}
          onSubmit={submit}
          className="grid gap-4 sm:grid-cols-2"
        >
          <Field
            label="Brand"
            name="brand"
            defaultValue={picked?.brand ?? template?.brand ?? 'Generic'}
            required
          />
          <Field
            label="Material name"
            name="materialName"
            defaultValue={picked?.materialName ?? template?.materialName ?? ''}
            required
          />
          <Field
            label="Material type"
            name="materialType"
            defaultValue={picked?.materialType ?? template?.materialType ?? 'PLA'}
            required
          />
          <ColorInputs defaultName={picked?.colorName ?? template?.colorName ?? ''} defaultHex={picked?.colorHex ?? template?.colorHex ?? '#808080'} />
          <LocationField defaultValue={template?.location ?? ''} />
          <Field label="Spool serial number" name="serialNumber" defaultValue="" />
          <Field label="Lot number" name="lotNumber" defaultValue={template?.lotNumber ?? ''} />
          <Field
            label="Diameter (mm)"
            name="diameterMm"
            type="number"
            step="0.001"
            defaultValue={picked?.diameterMm ?? template?.diameterMm ?? 1.75}
            required
          />
          <Field
            label="Density (g/cm³)"
            name="density"
            type="number"
            step="0.0001"
            defaultValue={picked?.density ?? template?.density ?? 1.24}
            required
          />
          <Field
            label="Initial net weight (g)"
            name="initialWeightG"
            type="number"
            step="0.1"
            defaultValue={picked?.nominalWeightG ?? template?.initialWeightG ?? 1000}
            required
          />
          <Field
            label="Initial length (m, optional)"
            name="initialLengthM"
            type="number"
            step="0.001"
            defaultValue={picked?.nominalLengthM ?? template?.initialLengthM ?? ''}
          />
          <Field
            label="Spool tare (g)"
            name="tareWeightG"
            type="number"
            step="0.1"
            defaultValue={picked?.tareWeightG ?? template?.tareWeightG ?? 0}
          />
          <Field
            label="Low-stock threshold (g)"
            name="lowStockWeightG"
            type="number"
            step="1"
            defaultValue={template?.lowStockWeightG ?? 100}
          />
          <Field
            label="Purchase price"
            name="purchasePrice"
            type="number"
            step="0.01"
            defaultValue={template?.purchasePrice ?? ''}
          />
          <Field label="Currency" name="currency" maxLength={3} defaultValue={template?.currency ?? 'EUR'} required />
          {error && (
            <p className="sm:col-span-2 text-sm text-destructive">{error}</p>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button
              variant="outline"
              type="button"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit">Save spool</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditSpoolDialog({ spool, open, onOpenChange, onUpdated }: { spool: Spool | null; open: boolean; onOpenChange: (open: boolean) => void; onUpdated: () => Promise<void> }) {
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spool) return;
    const f = new FormData(event.currentTarget);
    try {
      await api(`/api/spools/${spool.id}`, { method: 'PUT', body: JSON.stringify({
        brand: f.get('brand'), material_name: f.get('materialName'), material_type: f.get('materialType'),
        color_name: f.get('colorName'), color_hex: f.get('colorHex'), location: f.get('location'),
        lot_number: f.get('lotNumber'), serial_number: f.get('serialNumber'), diameter_mm: Number(f.get('diameterMm')),
        density_g_cm3: Number(f.get('density')), tare_weight_g: Number(f.get('tareWeightG')),
        low_stock_weight_g: Number(f.get('lowStockWeightG')), purchase_price: f.get('purchasePrice') ? Number(f.get('purchasePrice')) : null,
        currency: typeof f.get('currency') === 'string' ? (f.get('currency') as string).toUpperCase() : 'EUR',
      }) });
      await onUpdated();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Save failed'); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader><DialogTitle>Edit {spool?.code}</DialogTitle><DialogDescription className="sr-only">Edit spool metadata.</DialogDescription></DialogHeader>
        {spool && <form key={spool.id} onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Brand" name="brand" defaultValue={spool.brand} required />
          <Field label="Material name" name="materialName" defaultValue={spool.materialName} required />
          <Field label="Material type" name="materialType" defaultValue={spool.materialType} required />
          <ColorInputs defaultName={spool.colorName} defaultHex={spool.colorHex} />
          <LocationField defaultValue={spool.location} />
          <Field label="Spool serial number" name="serialNumber" defaultValue={spool.serialNumber} />
          <Field label="Lot number" name="lotNumber" defaultValue={spool.lotNumber} />
          <Field label="Diameter (mm)" name="diameterMm" type="number" step="0.001" defaultValue={spool.diameterMm} required />
          <Field label="Density (g/cm³)" name="density" type="number" step="0.0001" defaultValue={spool.density} required />
          <Field label="Spool tare (g)" name="tareWeightG" type="number" step="0.1" defaultValue={spool.tareWeightG} required />
          <Field label="Low-stock threshold (g)" name="lowStockWeightG" type="number" step="1" defaultValue={spool.lowStockWeightG} required />
          <Field label="Purchase price" name="purchasePrice" type="number" step="0.01" defaultValue={spool.purchasePrice ?? ''} />
          <Field label="Currency" name="currency" maxLength={3} defaultValue={spool.currency || 'EUR'} required />
          {error && <p className="sm:col-span-2 text-sm text-destructive">{error}</p>}
          <DialogFooter className="sm:col-span-2"><Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit">Save changes</Button></DialogFooter>
        </form>}
      </DialogContent>
    </Dialog>
  );
}

function AddPrinterDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => Promise<void>;
}) {
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    try {
      await api('/api/printers', {
        method: 'POST',
        body: JSON.stringify({
          name: f.get('name'),
          manufacturer: f.get('manufacturer'),
          model: f.get('model'),
          location: f.get('location'),
          slicer_profile: f.get('slicerProfile'),
          notes: f.get('notes'),
          preset: f.get('preset'),
        }),
      });
      onOpenChange(false);
      await onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Save failed');
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add printer</DialogTitle>
          <DialogDescription>
            Configure a printer and its tool layout.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Name" name="name" required />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Manufacturer" name="manufacturer" defaultValue="Prusa" />
            <Field label="Model" name="model" />
          </div>
          <LocationField />
          <Field label="PrusaSlicer profile name" name="slicerProfile" />
          <Field label="Notes" name="notes" />
          <div className="space-y-2">
            <Label htmlFor="preset">Tool preset</Label>
            <select
              id="preset"
              name="preset"
              className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
            >
              <option value="single">Single-tool</option>
              <option value="dual">Dual-extruder</option>
              <option value="indx8">INDX T1–T8</option>
            </select>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button
              variant="outline"
              type="button"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit">Save printer</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditPrinterDialog({ printer, open, onOpenChange, onUpdated }: { printer: Printer | null; open: boolean; onOpenChange: (open: boolean) => void; onUpdated: () => Promise<void> }) {
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!printer) return;
    const f = new FormData(event.currentTarget);
    try {
      await api(`/api/printers/${printer.id}`, { method: 'PUT', body: JSON.stringify({
        name: f.get('name'), manufacturer: f.get('manufacturer'), model: f.get('model'), location: f.get('location'),
        slicer_profile: f.get('slicerProfile'), notes: f.get('notes'),
      }) });
      await onUpdated();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Save failed'); }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Edit {printer?.code}</DialogTitle><DialogDescription className="sr-only">Edit printer details.</DialogDescription></DialogHeader>
        {printer && <form key={printer.id} onSubmit={submit} className="space-y-4">
          <Field label="Name" name="name" defaultValue={printer.name} required />
          <div className="grid grid-cols-2 gap-3"><Field label="Manufacturer" name="manufacturer" defaultValue={printer.manufacturer} /><Field label="Model" name="model" defaultValue={printer.model} /></div>
          <LocationField defaultValue={printer.location} />
          <Field label="PrusaSlicer profile name" name="slicerProfile" defaultValue={printer.slicerProfile} />
          <div className="space-y-2"><Label htmlFor="printerNotes">Notes</Label><textarea id="printerNotes" name="notes" defaultValue={printer.notes} className="min-h-24 w-full rounded-lg border bg-background px-3 py-2 text-sm" /></div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter><Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancel</Button><Button type="submit">Save changes</Button></DialogFooter>
        </form>}
      </DialogContent>
    </Dialog>
  );
}

function WeighDialog({
  spool,
  open,
  onOpenChange,
  onUpdated,
}: {
  spool: Spool | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => Promise<void>;
}) {
  const [error, setError] = useState('');
  const [mode, setMode] = useState<'weigh' | 'consume'>('weigh');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spool) return;
    const f = new FormData(event.currentTarget);
    const consumedWeight = Number(f.get('consumedWeightG'));
    const allowNegative = mode === 'consume' && consumedWeight > spool.remainingWeightG
      ? window.confirm(`${spool.code} will become negative. Record this inventory discrepancy?`)
      : false;
    if (mode === 'consume' && consumedWeight > spool.remainingWeightG && !allowNegative) return;
    try {
      await api(`/api/spools/${spool.id}/weigh`, {
        method: 'POST',
        body: JSON.stringify(mode === 'weigh'
          ? { total_weight_g: Number(f.get('totalWeightG')), note: f.get('note') }
          : { consumed_weight_g: consumedWeight, allow_negative: allowNegative, note: f.get('note') }),
      });
      await onUpdated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Weighing failed');
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Update {spool?.code} inventory</DialogTitle>
          <DialogDescription>
            Set the remaining amount by weighing, or subtract known filament usage.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-2 rounded-lg bg-muted p-1">
          <Button type="button" variant={mode === 'weigh' ? 'default' : 'ghost'} onClick={() => { setMode('weigh'); setError(''); }}>Weigh spool</Button>
          <Button type="button" variant={mode === 'consume' ? 'default' : 'ghost'} onClick={() => { setMode('consume'); setError(''); }}>Subtract usage</Button>
        </div>
        <form key={`${spool?.id}-${mode}`} className="space-y-4" onSubmit={submit}>
          {mode === 'weigh' ? (
            <Field label="Total weight including spool (g)" name="totalWeightG" type="number" min="0" step="0.1" required />
          ) : (
            <Field label="Filament used (g)" name="consumedWeightG" type="number" min="0.1" step="0.1" required />
          )}
          <Field label="Note" name="note" defaultValue={mode === 'weigh' ? 'Manual weighing' : 'Manual filament usage'} />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="submit">
              <Scale className="size-4" /> {mode === 'weigh' ? 'Apply correction' : 'Subtract usage'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RepurposeSpoolDialog({
  spool,
  open,
  onOpenChange,
  onUpdated,
}: {
  spool: Spool | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => Promise<void>;
}) {
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState('');
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [picked, setPicked] = useState<CatalogItem | null>(null);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => {
      if (query.trim().length >= 2 && !picked) {
        setSearching(true);
        api<CatalogItem[]>(`/api/catalog/search?q=${encodeURIComponent(query)}&limit=60`)
          .then((items) => {
            setCatalog(items);
            setSearched(true);
          })
          .catch(() => setCatalog([]))
          .finally(() => setSearching(false));
      } else if (query.trim().length < 2) {
        setCatalog([]);
        setSearched(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [picked, query]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spool) return;
    const f = new FormData(event.currentTarget);
    setSaving(true);
    setError('');
    try {
      await api(`/api/spools/${spool.id}/restore-and-repurpose`, {
        method: 'POST',
        body: JSON.stringify({
          confirmation: 'RESTORE_AND_REPURPOSE',
          brand: f.get('brand'),
          material_name: f.get('materialName'),
          material_type: f.get('materialType'),
          color_name: f.get('colorName'),
          color_hex: f.get('colorHex'),
          location: f.get('location'),
          lot_number: f.get('lotNumber'),
          serial_number: f.get('serialNumber'),
          diameter_mm: Number(f.get('diameterMm')),
          density_g_cm3: Number(f.get('density')),
          tare_weight_g: Number(f.get('tareWeightG')),
          initial_weight_g: Number(f.get('initialWeightG')),
          initial_length_m: f.get('initialLengthM') ? Number(f.get('initialLengthM')) : null,
          low_stock_weight_g: Number(f.get('lowStockWeightG')),
          purchase_price: f.get('purchasePrice') ? Number(f.get('purchasePrice')) : null,
          currency: typeof f.get('currency') === 'string' ? (f.get('currency') as string).toUpperCase() : 'EUR',
          note: 'Restored and repurposed after an incorrect setup entry',
          ...(picked ? {
            opt_brand_uuid: picked.opt.brandUuid,
            opt_material_uuid: picked.opt.materialUuid,
            opt_package_uuid: picked.opt.packageUuid,
            opt_container_uuid: picked.opt.containerUuid,
            catalog_snapshot: picked.raw,
          } : {}),
        }),
      });
      await onUpdated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Restore failed');
    } finally {
      setSaving(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Restore &amp; repurpose {spool?.code}</DialogTitle>
          <DialogDescription>
            Reassign this inactive setup record to a different physical spool. Its code and internal ID stay unchanged. This is blocked when print-job history exists.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="repurpose-catalog-search">Search OpenPrintTag</Label>
          <Input
            id="repurpose-catalog-search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPicked(null);
            }}
            placeholder="Brand, material, color, tag or GTIN"
          />
          {searching && <p className="text-xs text-muted-foreground">Searching…</p>}
          {catalog.length > 0 && !picked && <div className="max-h-64 overflow-auto rounded-xl border p-1">
            {catalog.map((item) => <button
              key={item.id}
              type="button"
              aria-label={`Select ${item.brand} ${item.materialName}`}
              onClick={() => {
                setPicked(item);
                setQuery(`${item.brand} ${item.materialName}`);
                setCatalog([]);
              }}
              className="flex w-full items-center gap-3 rounded-lg p-2 text-left hover:bg-muted"
            >
              <span className="size-7 shrink-0 rounded-lg border" style={{ background: item.colorHex }} />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{item.brand} · {item.materialName}</p>
                <p className="text-xs text-muted-foreground">{item.materialType} · {item.nominalWeightG ?? '?'} g · {item.colorHex.toUpperCase()}{item.gtin ? ` · GTIN ${item.gtin}` : ''}</p>
              </div>
            </button>)}
          </div>}
          {!searching && searched && catalog.length === 0 && !picked && <p className="text-xs text-muted-foreground">No matching OpenPrintTag material found. Try fewer words or enter the spool manually.</p>}
          {picked && <div className="flex items-center justify-between rounded-xl border bg-muted/40 px-3 py-2">
            <div className="flex min-w-0 items-center gap-2">
              <span className="size-6 shrink-0 rounded-md border" style={{ background: picked.colorHex }} />
              <p className="truncate text-sm font-semibold">{picked.brand} · {picked.materialName}</p>
            </div>
            <Button type="button" size="sm" variant="ghost" onClick={() => { setPicked(null); setQuery(''); }}>Clear</Button>
          </div>}
        </div>
        {spool && <form key={`${spool.id}-${picked?.id ?? 'manual'}`} onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Brand" name="brand" defaultValue={picked?.brand ?? 'Generic'} required />
          <Field label="Material name" name="materialName" defaultValue={picked?.materialName ?? ''} required />
          <Field label="Material type" name="materialType" defaultValue={picked?.materialType ?? 'PLA'} required />
          <ColorInputs defaultName={picked?.colorName ?? ''} defaultHex={picked?.colorHex ?? '#808080'} />
          <LocationField defaultValue={spool.location} />
          <Field label="Spool serial number" name="serialNumber" defaultValue="" />
          <Field label="Lot number" name="lotNumber" defaultValue="" />
          <Field label="Current filament weight (g)" name="initialWeightG" type="number" min="0" step="0.1" defaultValue={picked?.nominalWeightG ?? ''} required />
          <Field label="Current length (m, optional)" name="initialLengthM" type="number" min="0" step="0.001" defaultValue={picked?.nominalLengthM ?? ''} />
          <Field label="Spool tare (g)" name="tareWeightG" type="number" min="0" step="0.1" defaultValue={picked?.tareWeightG ?? 0} required />
          <Field label="Diameter (mm)" name="diameterMm" type="number" min="0.001" step="0.001" defaultValue={picked?.diameterMm ?? 1.75} required />
          <Field label="Density (g/cm³)" name="density" type="number" min="0.0001" step="0.0001" defaultValue={picked?.density ?? 1.24} required />
          <Field label="Low-stock threshold (g)" name="lowStockWeightG" type="number" min="0" step="1" defaultValue={100} required />
          <Field label="Purchase price" name="purchasePrice" type="number" min="0" step="0.01" defaultValue="" />
          <Field label="Currency" name="currency" maxLength={3} defaultValue="EUR" required />
          <label className="flex items-start gap-2 rounded-xl border bg-muted/40 p-3 text-sm sm:col-span-2">
            <input className="mt-0.5" type="checkbox" required />
            <span>I understand that {spool.code} keeps its existing audit and inventory ledger.</span>
          </label>
          {error && <p className="text-sm text-destructive sm:col-span-2">{error}</p>}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}><RotateCcw className="size-4" /> {saving ? 'Restoring…' : 'Restore & repurpose'}</Button>
          </DialogFooter>
        </form>}
      </DialogContent>
    </Dialog>
  );
}

function EmptySpoolDialog({
  spool,
  open,
  onOpenChange,
  onUpdated,
}: {
  spool: Spool | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => Promise<void>;
}) {
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  async function markEmpty() {
    if (!spool) return;
    setSaving(true);
    setError('');
    try {
      await api(`/api/spools/${spool.id}/empty`, { method: 'POST' });
      await onUpdated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Mark {spool?.code} empty?</DialogTitle>
          <DialogDescription>
            The remaining {formatWeight(spool?.remainingWeightG ?? 0)} will be
            corrected to zero. The spool will be unloaded and moved to the
            archived list. Its ledger and print history are preserved.
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={saving}
            onClick={markEmpty}
          >
            <Archive className="size-4" /> Mark empty
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function JobDialog({
  job,
  spools,
  printers,
  open,
  onOpenChange,
  onUpdated,
}: {
  job: Job;
  spools: Spool[];
  printers: Printer[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => Promise<void>;
}) {
  const [mapping, setMapping] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      job.usages.map((usage) => [
        usage.id,
        usage.mappedSpoolId || usage.suggestedSpoolId || '',
      ]),
    ),
  );
  const [actual, setActual] = useState<Record<string, number>>(() =>
    Object.fromEntries(
      job.usages.map((usage) => [
        usage.id,
        usage.actualWeightG || usage.estimatedWeightG,
      ]),
    ),
  );
  const [error, setError] = useState('');
  const [jobPrinter, setJobPrinter] = useState(job.printer.id);
  const [rankings, setRankings] = useState<Record<string, Spool[]>>({});
  useEffect(() => {
    let active = true;
    Promise.all(job.usages.map(async (usage) => [usage.id, await api<Spool[]>(`/api/spools/ranked?materialType=${encodeURIComponent(usage.materialType)}&colorHex=${encodeURIComponent(usage.colorHex)}`)] as const))
      .then((entries) => { if (active) setRankings(Object.fromEntries(entries)); })
      .catch(() => undefined);
    return () => { active = false; };
  }, [job.id, job.usages]);
  async function changePrinter() {
    try {
      await api(`/api/jobs/${job.id}/printer`, { method: 'PUT', body: JSON.stringify({ printer_id: jobPrinter }) });
      await onUpdated();
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Printer change failed'); }
  }
  async function saveMapping() {
    try {
      await api(`/api/jobs/${job.id}/mapping`, {
        method: 'PUT',
        body: JSON.stringify({
          mappings: job.usages.map((u) => ({
            usage_id: u.id,
            spool_id: mapping[u.id],
          })),
        }),
      });
      await onUpdated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Mapping failed');
    }
  }
  async function book(allowNegative = false) {
    try {
      await api(`/api/jobs/${job.id}/book`, {
        method: 'POST',
        body: JSON.stringify({
          usages: job.usages.map((u) => ({
            usage_id: u.id,
            actual_weight_g: actual[u.id],
          })),
          allow_negative: allowNegative,
        }),
      });
      await onUpdated();
    } catch (reason) {
      const message =
        reason instanceof Error ? reason.message : 'Booking failed';
      if (
        (message.includes('negative') || message.includes('negatief')) &&
        !allowNegative &&
        confirm(
          `${message}\n\nContinue and mark this as an inventory discrepancy?`,
        )
      )
        return book(true);
      setError(message);
    }
  }
  async function dismiss() {
    await api(`/api/jobs/${job.id}/dismiss`, { method: 'POST' });
    await onUpdated();
  }
  async function quickBook() {
    try { await api(`/api/jobs/${job.id}/confirm-and-book`, { method: 'POST' }); await onUpdated(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Quick booking failed'); }
  }
  const canQuickBook = job.status === 'NEW' && job.warnings.length === 0 && job.usages.length > 0 && job.usages.every((usage) => usage.suggestedSpoolId);
  const rankedSpools = (usage: Usage) => rankings[usage.id] ?? [...spools].sort((left, right) => {
    const materialRank = (row: Spool) => row.materialType.toLowerCase() === usage.materialType.toLowerCase() ? 0 : 1;
    const colorRank = (row: Spool) => row.colorHex.toLowerCase() === usage.colorHex.toLowerCase() ? 0 : 1;
    return materialRank(left) - materialRank(right) || colorRank(left) - colorRank(right) || right.availableWeightG - left.availableWeightG;
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{job.displayName}</DialogTitle>
          <DialogDescription>
            {job.code} · {job.printer.code}
          </DialogDescription>
        </DialogHeader>
        {(job.slicerProfile || job.routingMode === 'default') && (
          <p className="text-xs text-muted-foreground">PrusaSlicer: {job.slicerProfile || 'Unknown profile'} · {job.routingMode}</p>
        )}
        {['BOOKED', 'DISMISSED'].includes(job.status) && <p className="rounded-xl bg-muted p-3 text-sm">This job was {job.status.toLowerCase()} while it was open. The latest data is shown.</p>}
        {!['BOOKED', 'DISMISSED'].includes(job.status) && (
          <div className="flex gap-2 rounded-xl border p-3">
            <select className="h-10 min-w-0 flex-1 rounded-lg border bg-background px-3 text-sm" value={jobPrinter} onChange={(event) => setJobPrinter(event.target.value)}>
              {printers.filter((printer) => !printer.archived).map((printer) => <option key={printer.id} value={printer.id}>{printer.code} · {printer.name}</option>)}
            </select>
            <Button variant="outline" onClick={changePrinter} disabled={jobPrinter === job.printer.id}>Change printer</Button>
          </div>
        )}
        {job.warnings.length > 0 && (
          <div className="rounded-xl bg-orange-500/10 p-3 text-sm text-orange-700">
            {job.warnings.join(' · ')}
          </div>
        )}
        <div className="space-y-3">
          {job.usages.map((usage) => (
            <div
              key={usage.id}
              className="grid gap-3 rounded-xl border p-4 md:grid-cols-[72px_1fr_140px]"
            >
              <div>
                <Badge>{usage.toolLabel}</Badge>
                <p className="mt-2 text-xs text-muted-foreground">
                  {usage.materialType || 'Unknown'}
                </p>
              </div>
              <select
                className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
                value={mapping[usage.id] || ''}
                onChange={(e) =>
                  setMapping((value) => ({
                    ...value,
                    [usage.id]: e.target.value,
                  }))
                }
              >
                <option value="">Select physical spool</option>
                {rankedSpools(usage).map((spool) => (
                  <option key={spool.id} value={spool.id}>
                    {spool.code} · {spool.brand} {spool.materialName} · {spool.materialType} · {spool.colorName || spool.colorHex} ·{' '}
                    {formatWeight(spool.availableWeightG)} · {formatLength(spool.availableLengthM)}{spool.loadedOn ? ` · loaded ${spool.loadedOn.printerCode}/${spool.loadedOn.tool}${spool.id !== usage.suggestedSpoolId ? ' (will move)' : ''}` : ''}{spool.availableWeightG < usage.estimatedWeightG ? ' · insufficient stock' : ''}
                  </option>
                ))}
              </select>
              <div>
                <Label htmlFor={`weight-${usage.id}`} className="text-[11px]">
                  Actual usage (g)
                </Label>
                <Input
                  id={`weight-${usage.id}`}
                  type="number"
                  step="0.01"
                  value={actual[usage.id] ?? usage.estimatedWeightG}
                  onChange={(e) =>
                    setActual((value) => ({
                      ...value,
                      [usage.id]: Number(e.target.value),
                    }))
                  }
                />
              </div>
            </div>
          ))}
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {!['BOOKED', 'DISMISSED'].includes(job.status) && <DialogFooter>
          <Button variant="ghost" onClick={dismiss}>
            <Archive className="size-4" /> Dismiss
          </Button>
          {job.status === 'MAPPED' ? (
            <Button onClick={() => book(false)}>Book usage</Button>
          ) : (
            <><Button
              onClick={saveMapping}
              disabled={Object.values(mapping).some((value) => !value)}
            >
              Confirm mapping
            </Button>{canQuickBook && <Button onClick={quickBook}>Confirm suggested mapping &amp; book</Button>}</>
          )}
        </DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}
