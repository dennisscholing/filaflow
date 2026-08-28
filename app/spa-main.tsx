import React from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/open-sans/latin-400.css';
import '@fontsource/open-sans/latin-600.css';
import '@fontsource/open-sans/latin-700.css';
import './globals.css';
import { FilaFlowApp } from './filaflow-app';
import { SpoolDetailView } from './spools/[id]/page';

const match = window.location.pathname.match(/^\/spools\/([^/]+)\/?$/);
document.documentElement.classList.add('dark');
createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {match ? <SpoolDetailView id={decodeURIComponent(match[1])} /> : <FilaFlowApp />}
  </React.StrictMode>,
);
