import React from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { StartPage } from './pages/StartPage';
import { ReviewPage } from './pages/ReviewPage';
import { ReportPage } from './pages/ReportPage';
import { CriteriaPage } from './pages/CriteriaPage';
import { SharedPage } from './pages/SharedPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-bg text-fg">
        <header className="border-b border-line bg-white sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
            <Link to="/" className="font-bold text-lg text-primary flex items-center gap-2">
              <span>🛡️</span>
              <span>보증금지킴</span>
            </Link>
            <nav className="flex items-center gap-4 text-sm">
              <Link to="/criteria" className="text-muted hover:text-fg">
                판정 기준
              </Link>
              <Link
                to="/"
                className="px-3 py-1.5 rounded bg-primary text-white text-sm font-medium hover:opacity-90"
              >
                검토 시작
              </Link>
            </nav>
          </div>
        </header>

        <main className="flex-1">
          <Routes>
            <Route path="/" element={<StartPage />} />
            <Route path="/review/:id" element={<ReviewPage />} />
            <Route path="/review/:id/report" element={<ReportPage />} />
            <Route path="/criteria" element={<CriteriaPage />} />
            <Route path="/s/:token" element={<SharedPage />} />
            <Route
              path="*"
              element={
                <div className="p-12 text-center">
                  <h2 className="text-xl font-bold mb-2">페이지를 찾을 수 없습니다</h2>
                  <Link to="/" className="text-primary underline">
                    시작 화면으로 이동
                  </Link>
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
};
