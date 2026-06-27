import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import { DashboardProvider } from "./context/DashboardContext";
import ToastContainer from "./components/common/ToastContainer";

import Dashboard from "./pages/Dashboard";
import Analysis from "./pages/Analysis";
import Recommendation from "./pages/Recommendation";
import History from "./pages/History";
import NotFound from "./pages/NotFound";

function App() {
  return (
    <BrowserRouter>
      <DashboardProvider>
        <Routes>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/recommendation" element={<Recommendation />} />
            <Route path="/history" element={<History />} />
            <Route path="/customers" element={<Dashboard />} />
            <Route path="/knowledge" element={<Dashboard />} />
            <Route path="/settings" element={<Dashboard />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
        <ToastContainer />
      </DashboardProvider>
    </BrowserRouter>
  );
}

export default App;
