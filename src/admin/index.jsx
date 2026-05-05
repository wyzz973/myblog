import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext.jsx';
import Login from './Login.jsx';
import Layout from './Layout.jsx';
import Dashboard from './Dashboard.jsx';
import Analytics from './Analytics.jsx';
import Posts from './Posts.jsx';
import Media from './Media.jsx';
import Comments from './Comments.jsx';
import Tags from './Tags.jsx';
import Site from './Site.jsx';
import Profile from './Profile.jsx';
import Contacts from './Contacts.jsx';
import Projects from './Projects.jsx';
import Now from './Now.jsx';
import Pet from './Pet.jsx';
import PetConversationDetail from './pet/PetConversationDetail.jsx';
import Settings from './Settings.jsx';
import ActivityLog from './ActivityLog.jsx';
import SiteIdentity from './SiteIdentity.jsx';
import Inbox from './Inbox.jsx';

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
          <Route path="analytics" element={<Analytics />} />
          <Route path="posts" element={<Posts />} />
          <Route path="media" element={<Media />} />
          <Route path="comments" element={<Comments />} />
          <Route path="tags" element={<Tags />} />
          <Route path="site" element={<Site />} />
          <Route path="profile" element={<Profile />} />
          <Route path="contacts" element={<Contacts />} />
          <Route path="projects" element={<Projects />} />
          <Route path="now" element={<Now />} />
          <Route path="pet" element={<Pet />} />
          <Route path="pet/conversations/:visitorHash" element={<PetConversationDetail />} />
          <Route path="settings" element={<Settings />} />
          <Route path="activity-log" element={<ActivityLog />} />
          <Route path="site-identity" element={<SiteIdentity />} />
          <Route path="inbox" element={<Inbox />} />
        </Route>
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AuthProvider>
  );
}
