import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as SDK from 'azure-devops-extension-sdk';
import '../index.css';
import { AdoApp } from './AdoApp';

// Dedicated entry point for the Azure DevOps extension hub. The standalone
// app's entry (src/main.tsx) is untouched and never runs the ADO SDK.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false },
  },
});

function render() {
  createRoot(document.getElementById('root')!).render(
    <QueryClientProvider client={queryClient}>
      <AdoApp />
    </QueryClientProvider>
  );
}

// Complete the Azure DevOps host handshake, then render and report success.
// `init({ loaded: false })` defers the "loaded" signal until React has mounted.
// If the handshake never completes — e.g. the bundle is opened outside Azure
// DevOps for local preview — fall back to rendering anyway so the page isn't
// blank.
async function boot() {
  try {
    SDK.init({ loaded: false });
    await Promise.race([
      SDK.ready(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('Azure DevOps SDK handshake timed out')), 2000),
      ),
    ]);
    render();
    SDK.notifyLoadSucceeded();
  } catch {
    render();
  }
}

boot();
