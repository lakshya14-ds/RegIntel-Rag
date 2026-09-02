import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { Home } from './pages/Home';
import { Ask } from './pages/Ask';
import { Search } from './pages/Search';
import { Latest } from './pages/Latest';
import { Compare } from './pages/Compare';
import { Document } from './pages/Document';
import { Timeline } from './pages/Timeline';
import { About } from './pages/About';

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Home />} />
            <Route path="ask" element={<Ask />} />
            <Route path="search" element={<Search />} />
            <Route path="latest" element={<Latest />} />
            <Route path="compare" element={<Compare />} />
            <Route path="document/:documentId" element={<Document />} />
            <Route path="document/:documentId/timeline" element={<Timeline />} />
            <Route path="about" element={<About />} />
            {/* Fallback to home */}
            <Route path="*" element={<Home />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
};

export default App;
