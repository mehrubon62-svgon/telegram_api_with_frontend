import { Component, type ReactNode } from 'react';

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('Render error:', error, info);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="flex min-h-dvh w-full items-start justify-center bg-bg p-6 text-text">
          <div className="max-w-2xl rounded-xl border border-danger/40 bg-danger/10 p-4 text-sm">
            <div className="mb-2 font-medium text-danger">Render error</div>
            <pre className="thin-scrollbar overflow-auto whitespace-pre-wrap break-words text-xs">
              {this.state.error.stack ?? this.state.error.message}
            </pre>
            <button
              onClick={() => {
                localStorage.removeItem('tg-auth');
                localStorage.removeItem('tg-ui');
                location.reload();
              }}
              className="mt-3 rounded bg-danger px-3 py-1.5 text-white"
            >
              Reset & reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
