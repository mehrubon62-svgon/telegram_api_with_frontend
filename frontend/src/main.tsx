import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/globals.css';
import { App } from './pages/App';

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
