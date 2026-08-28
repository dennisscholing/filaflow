'use client';

import { useEffect, useState } from 'react';
import { ArrowLeft, Boxes, Scale } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

type Ledger = {
  id: string;
  kind: string;
  weightDeltaG: number;
  lengthDeltaM: number;
  note: string;
  createdAt: string;
};
type Detail = {
  id: string;
  code: string;
  brand: string;
  materialName: string;
  materialType: string;
  colorName: string;
  colorHex: string;
  remainingWeightG: number;
  remainingLengthM: number;
  remainingPercent: number;
  reservedWeightG: number;
  availableWeightG: number;
  location: string;
  loadedOn?: { printer: string; tool: string } | null;
  ledger: Ledger[];
};

export function SpoolDetailView({ id }: { id: string }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    void fetch(`/api/spools/${id}`, { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(
            response.status === 401
              ? 'Sign in from the main page first.'
              : 'Spool not found',
          );
        return response.json() as Promise<Detail>;
      })
      .then(setDetail)
      .catch((reason: unknown) =>
        setError(
          reason instanceof Error ? reason.message : 'Spool not found',
        ),
      );
  }, [id]);
  if (error)
    return (
      <main className="grid min-h-screen place-items-center bg-background p-6">
        <div className="text-center">
          <Boxes className="mx-auto size-10 text-muted-foreground" />
          <h1 className="mt-4 text-xl font-bold">{error}</h1>
          <Button className="mt-5" onClick={() => (location.href = '/')}>
            Go to FilaFlow
          </Button>
        </div>
      </main>
    );
  if (!detail)
    return (
      <main className="grid min-h-screen place-items-center bg-background">
        Loading…
      </main>
    );
  return (
    <main className="min-h-screen bg-background p-5 text-foreground md:p-10">
      <div className="mx-auto max-w-3xl">
        <Button variant="ghost" onClick={() => history.back()}>
          <ArrowLeft /> Back
        </Button>
        <section className="mt-5 overflow-hidden rounded-3xl border bg-card shadow-sm">
          <div className="h-28" style={{ background: detail.colorHex }} />
          <div className="p-6 md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <Badge className="font-mono">{detail.code}</Badge>
                <h1 className="mt-3 text-3xl font-bold">
                  {detail.brand} {detail.materialName}
                </h1>
                <p className="mt-1 text-muted-foreground">
                  {detail.materialType} · {detail.colorName || detail.colorHex}{' '}
                  · {detail.location || 'No location'}
                </p>
              </div>
              <div className="text-right">
                <p className="text-4xl font-bold">{detail.remainingPercent}%</p>
                <p className="text-sm text-muted-foreground">remaining</p>
              </div>
            </div>
            <Progress
              value={Math.max(0, detail.remainingPercent)}
              className="mt-7 h-2"
            />
            <div className="mt-7 grid gap-3 sm:grid-cols-3">
              {[
                ['Remaining', `${detail.remainingWeightG} g`],
                ['Reserved', `${detail.reservedWeightG} g`],
                ['Available', `${detail.availableWeightG} g`],
              ].map(([label, value]) => (
                <div key={label} className="rounded-2xl bg-muted p-4">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="mt-1 text-xl font-bold">{value}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Length: {detail.remainingLengthM.toLocaleString('en-US')} m{' '}
              {detail.loadedOn
                ? `· loaded on ${detail.loadedOn.printer} ${detail.loadedOn.tool}`
                : ''}
            </p>
          </div>
        </section>
        <section className="mt-6 rounded-3xl border bg-card p-6">
          <div className="flex items-center gap-2">
            <Scale className="size-5" />
            <h2 className="font-bold">Inventory history</h2>
          </div>
          <div className="mt-4 divide-y">
            {detail.ledger.map((entry) => (
              <div
                key={entry.id}
                className="flex items-center justify-between gap-4 py-3"
              >
                <div>
                  <p className="text-sm font-semibold">{entry.note}</p>
                  <p className="text-xs text-muted-foreground">
                    {entry.kind} ·{' '}
                    {new Date(entry.createdAt).toLocaleString('en-US')}
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={`font-mono text-sm ${entry.weightDeltaG < 0 ? 'text-orange-600' : 'text-emerald-600'}`}
                  >
                    {entry.weightDeltaG > 0 ? '+' : ''}
                    {entry.weightDeltaG} g
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {entry.lengthDeltaM > 0 ? '+' : ''}
                    {entry.lengthDeltaM} m
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

export default function SpoolDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [id, setId] = useState('');
  useEffect(() => {
    void params.then((value) => setId(value.id));
  }, [params]);
  return id ? (
    <SpoolDetailView id={id} />
  ) : (
    <main className="grid min-h-screen place-items-center bg-background">
      Loading…
    </main>
  );
}
