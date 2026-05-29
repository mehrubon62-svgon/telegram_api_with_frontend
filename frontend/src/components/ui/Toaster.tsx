import { Toaster as SonnerToaster, toast as sonnerToast } from 'sonner';

export function Toaster() {
  return <SonnerToaster richColors position="top-center" closeButton />;
}

export const toast = sonnerToast;
