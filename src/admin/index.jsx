import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext.jsx';
import Login from './Login.jsx';
import Layout, { ComingSoon } from './Layout.jsx';
import Dashboard from './Dashboard.jsx';

// Wrap a protected element. If no token → bounce to /admin (login),
// preserving the original path so we can redirect back after login.
function RequireAuth({ children }) {
  const { isAuthed } = useAuth();
  const location = useLocation();
  if (!isAuthed) {
    return (
      <Navigate
        to="/admin"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }
  return children;
}

// If already logged in and the user lands on /admin (login), forward them.
function PublicOnly({ children }) {
  const { isAuthed } = useAuth();
  if (isAuthed) return <Navigate to="/admin/dashboard" replace />;
  return children;
}

export default function AdminApp() {
  return (
    <AuthProvider>
      <Routes>
        <Route
          index
          element={
            <PublicOnly>
              <Login />
            </PublicOnly>
          }
        />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="analytics" element={<ComingSoon title="Analytics" />} />
          <Route path="posts" element={<ComingSoon title="Posts" />} />
          <Route path="media" element={<ComingSoon title="Media" />} />
          <Route path="comments" element={<ComingSoon title="Comments" />} />
          <Route path="tags" element={<ComingSoon title="Tags" />} />
          <Route path="site" element={<ComingSoon title="Site" />} />
          <Route path="profile" element={<ComingSoon title="Profile" />} />
          <Route path="contacts" element={<ComingSoon title="Contacts" />} />
          <Route path="projects" element={<ComingSoon title="Projects" />} />
          <Route path="now" element={<ComingSoon title="Now" />} />
          <Route path="pet" element={<ComingSoon title="Pet" />} />
          <Route path="settings" element={<ComingSoon title="Settings" />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AuthProvider>
  );
}
