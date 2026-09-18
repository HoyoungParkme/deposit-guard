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
        <main className="flex-1 flex flex-col">
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
