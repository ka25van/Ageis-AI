import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './lib/AuthContext'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Projects } from './pages/Projects'
import { Repositories } from './pages/Repositories'
import { Knowledge } from './pages/Knowledge'
import { Agents } from './pages/Agents'
import { ApprovalQueue } from './pages/ApprovalQueue'
import { Settings } from './pages/Settings'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/repositories" element={<Repositories />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/approvals" element={<ApprovalQueue />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
