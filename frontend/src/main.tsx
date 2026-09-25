import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import App from './App.tsx';
import Family from './Family.tsx';

// Two audiences, two pages. The family arrives at a link to one person and
// should never see the tuning console; a router would be more than this needs.
const family = window.location.pathname.match(/^\/family\/([\w-]+)/);

createRoot(document.getElementById('root')!).render(
  <StrictMode>{family ? <Family seniorId={family[1]} /> : <App />}</StrictMode>,
);
