'use client';

/* oxlint-disable typescript/no-deprecated -- React form handlers use the framework's FormEvent type. */

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Archive,
  Boxes,
  ChevronRight,
  CircleGauge,
  CloudDownload,
  Database,
  Download,
  Inbox,
  Layers3,
  LogOut,
  Plus,
  Printer as PrinterIcon,
  RefreshCw,
  Scale,
  Search,
  Settings,
  SlidersHorizontal,
  UserPlus,
  Users,
  Warehouse,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
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

type NavKey = 'overview' | 'spools' | 'printers' | 'jobs' | 'settings';
type User = {
  id: string;
  email: string;
  displayName: string;
  role: string;
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
  initialWeightG: number;
  remainingWeightG: number;
  reservedWeightG: number;
  availableWeightG: number;
  initialLengthM: number;
  remainingLengthM: number;
  reservedLengthM: number;
  remainingPercent: number;
  lowStock: boolean;
  archived: boolean;
  discrepancy: boolean;
  loadedOn?: { printer: string; printerCode: string; tool: string } | null;
};
type SpoolFilters = {
  brand: string;
  material: string;
  color: string;
  location: string;
  loadState: string;
  stockState: string;
  printer: string;
};
const EMPTY_SPOOL_FILTERS: SpoolFilters = {
  brand: '',
  material: '',
  color: '',
  location: '',
  loadState: '',
  stockState: '',
  printer: '',
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
  };
};
type Printer = {
  id: string;
  code: string;
  name: string;
  manufacturer: string;
  model: string;
  slicerProfile: string;
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
  printer: { code: string; name: string };
  usages: Usage[];
};
type Dashboard = {
  summary: {
    remainingWeightG: number;
    remainingLengthM: number;
    reservedWeightG: number;
    reservedLengthM: number;
    availableWeightG: number;
    availableLengthM: number;
    activeSpools: number;
    lowStockSpools: number;
    loadedSpools: number;
    openJobs: number;
  };
  spools: Spool[];
  printers: Printer[];
  jobs: Job[];
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
  const [printerDialog, setPrinterDialog] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

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
  }, []);
  useEffect(() => {
    api<User>('/api/auth/me')
      .then((me) => {
        setUser(me);
        return refresh();
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, [refresh]);
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
      await refresh();
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
                onClick={() => setActive(key)}
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
              {active === 'spools' && (
                <Button
                  className="rounded-xl"
                  onClick={() => setSpoolDialog(true)}
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
                onNavigate={setActive}
                onJob={setSelectedJob}
              />
            )}
            {active === 'spools' && (
              <SpoolsView
                spools={spools}
                onRefresh={refresh}
                onAdd={() => setSpoolDialog(true)}
              />
            )}
            {active === 'printers' && (
              <PrintersView
                printers={printers}
                spools={spools}
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
            onClick={() => setActive(key)}
            className={`flex min-w-12 flex-col items-center gap-1 rounded-lg px-2 py-1 text-[10px] ${active === key ? 'text-primary' : 'text-muted-foreground'}`}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </nav>
      <AddSpoolDialog
        open={spoolDialog}
        onOpenChange={setSpoolDialog}
        onCreated={refresh}
      />
      <AddPrinterDialog
        open={printerDialog}
        onOpenChange={setPrinterDialog}
        onCreated={refresh}
      />
      {selectedJob && (
        <JobDialog
          key={selectedJob.id}
          job={selectedJob}
          spools={spools}
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
  onNavigate,
  onJob,
}: {
  dashboard: Dashboard;
  onNavigate: (key: NavKey) => void;
  onJob: (job: Job) => void;
}) {
  const s = dashboard.summary;
  const metrics = [
    {
      label: 'Remaining',
      value: formatWeight(s.remainingWeightG),
      note: formatLength(s.remainingLengthM),
      icon: Warehouse,
    },
    {
      label: 'Reserved',
      value: formatWeight(s.reservedWeightG),
      note: formatLength(s.reservedLengthM),
      icon: Layers3,
    },
    {
      label: 'Available',
      value: formatWeight(s.availableWeightG),
      note: formatLength(s.availableLengthM),
      icon: CircleGauge,
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
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ label, value, note, icon: Icon }) => (
          <article
            key={label}
            className="rounded-2xl border bg-card p-5 shadow-sm"
          >
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
          </article>
        ))}
      </section>
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
                .map((spool) => <SpoolCard key={spool.id} spool={spool} />)
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
      <TrendPanel />
    </div>
  );
}
function SpoolCard({ spool }: { spool: Spool }) {
  return (
    <article className="rounded-2xl border bg-background p-4">
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
            {formatWeight(spool.remainingWeightG)} ·{' '}
            {formatLength(spool.remainingLengthM)}
          </p>
        </div>
        <span
          className={`text-xs font-semibold ${spool.archived ? 'text-muted-foreground' : spool.lowStock ? 'text-orange-600' : 'text-emerald-600'}`}
        >
          {spool.archived ? 'Inactive' : spool.lowStock ? 'Low' : 'Available'}
        </span>
      </div>
      <Progress
        value={Math.max(0, spool.remainingPercent)}
        className="mt-3 h-1.5"
      />
      {spool.loadedOn && (
        <p className="mt-3 truncate text-[11px] text-muted-foreground">
          Loaded: {spool.loadedOn.printerCode} · {spool.loadedOn.tool}
        </p>
      )}
    </article>
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
              <div className="mt-5 grid grid-cols-4 gap-2">
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
  const data = [28, 44, 22, 61, 48, 76, 53, 82, 65, 91, 58, 72];
  return (
    <section className="rounded-2xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-bold">Usage this month</h2>
        <Badge variant="secondary">30 days</Badge>
      </div>
      <div className="mt-6 flex h-32 items-end gap-2">
        {data.map((height, index) => (
          <div
            key={index}
            className="flex-1 rounded-t-md bg-primary/20 transition hover:bg-primary"
            style={{ height: `${height}%` }}
          />
        ))}
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
  onRefresh,
  onAdd,
}: {
  spools: Spool[];
  onRefresh: () => Promise<void>;
  onAdd: () => void;
}) {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SpoolFilters>(EMPTY_SPOOL_FILTERS);
  const [weigh, setWeigh] = useState<Spool | null>(null);
  const [emptySpool, setEmptySpool] = useState<Spool | null>(null);
  const [archivedSpools, setArchivedSpools] = useState<Spool[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [loadingArchived, setLoadingArchived] = useState(false);
  const [listError, setListError] = useState('');
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
  const filtered = useMemo(
    () =>
      visibleSpools.filter((spool) => {
        const matchesQuery = `${spool.code} ${spool.brand} ${spool.materialName} ${spool.materialType} ${spool.colorName} ${spool.colorHex} ${spool.location} ${spool.loadedOn?.printer ?? ''} ${spool.loadedOn?.printerCode ?? ''}`
          .toLowerCase()
          .includes(query.trim().toLowerCase());
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
        );
      }),
    [visibleSpools, query, filters],
  );
  const activeFilterCount = Object.values(filters).filter(Boolean).length;
  function updateFilter(key: keyof SpoolFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
  }
  function clearFilters() {
    setQuery('');
    setFilters({ ...EMPTY_SPOOL_FILTERS });
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
        </div>
      </div>
      {listError && <p className="text-sm text-destructive">{listError}</p>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {filtered.map((spool) => (
          <article
            key={spool.id}
            className="rounded-2xl border bg-card p-1 shadow-sm"
          >
            <SpoolCard spool={spool} />
            <div
              className={`grid gap-2 p-3 pt-0 ${spool.archived ? 'grid-cols-1' : 'grid-cols-3'}`}
            >
              {!spool.archived && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setWeigh(spool)}
                >
                  <Scale className="size-4" /> Weigh
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  window.open(`/api/spools/${spool.id}/label.svg`, '_blank')
                }
              >
                <Download className="size-4" /> Label
              </Button>
              {!spool.archived && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  onClick={() => setEmptySpool(spool)}
                >
                  <Archive className="size-4" /> Empty
                </Button>
              )}
            </div>
          </article>
        ))}
        {!filtered.length && <Empty text="No spools found." />}
      </div>
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
    </div>
  );
}
function PrintersView({
  printers,
  spools,
  onRefresh,
}: {
  printers: Printer[];
  spools: Spool[];
  onRefresh: () => Promise<void>;
}) {
  async function load(printerId: string, toolId: string, spoolId: string) {
    await api(`/api/printers/${printerId}/tools/${toolId}/loadout`, {
      method: 'PUT',
      body: JSON.stringify({ spool_id: spoolId || null }),
    });
    await onRefresh();
  }
  return (
    <div className="grid gap-5 xl:grid-cols-2">
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
            </div>
            <Badge>{printer.tools.length} tools</Badge>
          </div>
          <div className="space-y-2 p-4">
            {printer.tools.map((tool) => (
              <div
                key={tool.id}
                className="grid grid-cols-[52px_1fr] items-center gap-3 rounded-xl bg-muted/60 p-3"
              >
                <div className="text-center">
                  <span
                    className="mx-auto block size-7 rounded-lg border"
                    style={{
                      background: tool.loadedSpool?.colorHex || 'transparent',
                    }}
                  />
                  <p className="mt-1 font-mono text-[10px]">{tool.label}</p>
                </div>
                <select
                  className="h-10 w-full rounded-lg border bg-background px-3 text-sm"
                  value={tool.loadedSpool?.id || ''}
                  onChange={(e) => load(printer.id, tool.id, e.target.value)}
                >
                  <option value="">No spool loaded</option>
                  {spools.map((spool) => (
                    <option key={spool.id} value={spool.id}>
                      {spool.code} · {spool.brand} {spool.materialName} ·{' '}
                      {formatWeight(spool.remainingWeightG)}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </article>
      ))}
      {!printers.length && (
        <Empty text="No printers configured." />
      )}
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
              {job.printer.code} · {job.filename}
            </p>
          </div>
          <div>
            <p className="text-sm font-semibold">
              {job.usages.length} tool{job.usages.length === 1 ? '' : 's'}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatWeight(
                job.usages.reduce((s, u) => s + u.estimatedWeightG, 0),
              )}
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
  onLogout,
}: {
  user: User;
  printers: Printer[];
  onLogout: () => void;
}) {
  const [message, setMessage] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [token, setToken] = useState('');
  const [tokenPrinterId, setTokenPrinterId] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [userDialog, setUserDialog] = useState(false);
  const [userError, setUserError] = useState('');
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
  const configureCommand =
    token && tokenPrinterId
      ? `python filaflow_hook.py --configure "${typeof window === 'undefined' ? '' : window.location.origin}" "${tokenPrinterId}" "${token}"`
      : '';
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="rounded-2xl border bg-card p-5">
        <h2 className="font-bold">Account</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {user.displayName} · {user.email} · {user.role}
        </p>
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
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    {account.email}
                  </p>
                </div>
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
        </section>
      )}
      {user.role === 'admin' && (
        <>
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
      <AddUserDialog
        open={userDialog}
        onOpenChange={setUserDialog}
        onCreated={loadUsers}
      />
    </div>
  );
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

function ColorField({ defaultValue }: { defaultValue: string }) {
  const [value, setValue] = useState(defaultValue);
  return (
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
  );
}

function AddSpoolDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => Promise<void>;
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
      ...(picked
        ? {
            opt_brand_uuid: picked.opt.brandUuid,
            opt_material_uuid: picked.opt.materialUuid,
            opt_package_uuid: picked.opt.packageUuid,
            opt_container_uuid: picked.opt.containerUuid,
            catalog_snapshot: picked.raw,
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
          key={picked?.id ?? 'manual'}
          onSubmit={submit}
          className="grid gap-4 sm:grid-cols-2"
        >
          <Field
            label="Brand"
            name="brand"
            defaultValue={picked?.brand ?? 'Generic'}
            required
          />
          <Field
            label="Material name"
            name="materialName"
            defaultValue={picked?.materialName ?? ''}
            required
          />
          <Field
            label="Material type"
            name="materialType"
            defaultValue={picked?.materialType ?? 'PLA'}
            required
          />
          <Field
            label="Color name"
            name="colorName"
            defaultValue={picked?.colorName ?? ''}
          />
          <ColorField defaultValue={picked?.colorHex ?? '#808080'} />
          <Field label="Storage location" name="location" />
          <Field label="Spool serial number" name="serialNumber" />
          <Field label="Lot number" name="lotNumber" />
          <Field
            label="Diameter (mm)"
            name="diameterMm"
            type="number"
            step="0.001"
            defaultValue={picked?.diameterMm ?? 1.75}
            required
          />
          <Field
            label="Density (g/cm³)"
            name="density"
            type="number"
            step="0.0001"
            defaultValue={picked?.density ?? 1.24}
            required
          />
          <Field
            label="Initial net weight (g)"
            name="initialWeightG"
            type="number"
            step="0.1"
            defaultValue={picked?.nominalWeightG ?? 1000}
            required
          />
          <Field
            label="Initial length (m, optional)"
            name="initialLengthM"
            type="number"
            step="0.001"
            defaultValue={picked?.nominalLengthM ?? ''}
          />
          <Field
            label="Spool tare (g)"
            name="tareWeightG"
            type="number"
            step="0.1"
            defaultValue={picked?.tareWeightG ?? 0}
          />
          <Field
            label="Low-stock threshold (g)"
            name="lowStockWeightG"
            type="number"
            step="1"
            defaultValue="100"
          />
          <Field
            label="Purchase price (€)"
            name="purchasePrice"
            type="number"
            step="0.01"
          />
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
          slicer_profile: f.get('slicerProfile'),
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
          <Field label="PrusaSlicer profile name" name="slicerProfile" />
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
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!spool) return;
    const f = new FormData(event.currentTarget);
    try {
      await api(`/api/spools/${spool.id}/weigh`, {
        method: 'POST',
        body: JSON.stringify({
          total_weight_g: Number(f.get('totalWeightG')),
          note: f.get('note'),
        }),
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
          <DialogTitle>Weigh {spool?.code}</DialogTitle>
          <DialogDescription>
            Enter the total weight including the spool.
          </DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={submit}>
          <Field
            label="Total weight (g)"
            name="totalWeightG"
            type="number"
            step="0.1"
            required
          />
          <Field label="Note" name="note" defaultValue="Manual weighing" />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button type="submit">
              <Scale className="size-4" /> Apply correction
            </Button>
          </DialogFooter>
        </form>
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
  open,
  onOpenChange,
  onUpdated,
}: {
  job: Job;
  spools: Spool[];
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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{job.displayName}</DialogTitle>
          <DialogDescription>
            {job.code} · {job.printer.code}
          </DialogDescription>
        </DialogHeader>
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
                {spools.map((spool) => (
                  <option key={spool.id} value={spool.id}>
                    {spool.code} · {spool.brand} {spool.materialName} ·{' '}
                    {formatWeight(spool.availableWeightG)}
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
        <DialogFooter>
          <Button variant="ghost" onClick={dismiss}>
            <Archive className="size-4" /> Dismiss
          </Button>
          {job.status === 'MAPPED' ? (
            <Button onClick={() => book(false)}>Book usage</Button>
          ) : (
            <Button
              onClick={saveMapping}
              disabled={Object.values(mapping).some((value) => !value)}
            >
              Confirm mapping
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
