import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import AdvancedWorkflows from "./pages/AdvancedWorkflows";
import Chat from "./pages/Chat";
import Dashboard from "./pages/Dashboard";
import EvidenceCollection from "./pages/EvidenceCollection";
import PolicyEnforcer from "./pages/PolicyEnforcer";
import Reports from "./pages/Reports";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="chat" element={<Chat />} />
        <Route path="evidence" element={<EvidenceCollection />} />
        <Route path="policy" element={<PolicyEnforcer />} />
        <Route path="reports" element={<Reports />} />
        <Route path="advanced" element={<AdvancedWorkflows />} />
      </Route>
    </Routes>
  );
}

export default App;
