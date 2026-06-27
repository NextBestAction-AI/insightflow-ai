import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import { DashboardProvider } from "./context/DashboardContext";

import ToastContainer from "./components/common/ToastContainer";


import Dashboard from "./pages/Dashboard";
import Analysis from "./pages/Analysis";
import Recommendation from "./pages/Recommendation";
import History from "./pages/History";
import NotFound from "./pages/NotFound";

import CommandCenter from "./pages/CommandCenter";
import Insights from "./pages/Insights";
import DecisionCenter from "./pages/DecisionCenter";


function App() {
  return (
    <BrowserRouter>

      <DashboardProvider>

        <Routes>


          {/* Common Layout */}
          <Route element={<MainLayout />}>


            {/* Default */}
            <Route
              path="/"
              element={<Navigate to="/dashboard" replace />}
            />


            {/* Main Dashboard */}
            <Route
              path="/dashboard"
              element={<Dashboard />}
            />


            {/* Customers */}
            <Route
              path="/customers"
              element={<CommandCenter />}
            />


            {/* AI Agents */}
            <Route
              path="/analysis"
              element={<Analysis />}
            />


            {/* Knowledge Base */}
            <Route
              path="/knowledge"
              element={<Insights />}
            />


            {/* Recommendations */}
            <Route
              path="/recommendation"
              element={<Recommendation />}
            />


            {/* History */}
            <Route
              path="/history"
              element={<History />}
            />


            {/* Settings */}
            <Route
              path="/settings"
              element={<DecisionCenter />}
            />


          </Route>



          {/* 404 */}
          <Route
            path="*"
            element={<NotFound />}
          />


        </Routes>


        <ToastContainer />


      </DashboardProvider>

    </BrowserRouter>
  );
}


export default App;