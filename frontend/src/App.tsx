import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import SubmitDispute from './pages/SubmitDispute';
import DisputeDetail from './pages/DisputeDetail';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/submit" element={<SubmitDispute />} />
          <Route path="/disputes/:id" element={<DisputeDetail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
