import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Login } from './pages/Login'
import { Register } from './pages/Register'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/projects" element={<div>Projects</div>} />
        <Route path="/repositories" element={<div>Repositories</div>} />
        <Route path="/knowledge" element={<div>Knowledge</div>} />
        <Route path="/agents" element={<div>Agents</div>} />
        <Route path="/settings" element={<div>Settings</div>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App