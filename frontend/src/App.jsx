import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/Navbar'
import RoleGuard from './components/RoleGuard'
import Login from './pages/Login'
import Chat from './pages/Chat'
import Stock from './pages/Stock'
import CRM from './pages/CRM'
import Notifications from './pages/Notifications'
import Admin from './pages/Admin'

function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Navbar />
      <Outlet />
    </div>
  )
}

function AuthRedirect() {
  const { user } = useAuth()
  return user ? <Navigate to="/chat" replace /> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RoleGuard>
                <Layout />
              </RoleGuard>
            }
          >
            <Route path="/chat" element={<Chat />} />
            <Route path="/stock" element={<Stock />} />
            <Route path="/crm" element={<CRM />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route
              path="/admin"
              element={
                <RoleGuard roles={['admin']}>
                  <Admin />
                </RoleGuard>
              }
            />
          </Route>
          <Route path="*" element={<AuthRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
