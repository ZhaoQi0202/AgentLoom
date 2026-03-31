/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ALLOW_BROWSER?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface Window {
  electronAPI?: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    checkBackend: () => Promise<boolean>;
  };
}
