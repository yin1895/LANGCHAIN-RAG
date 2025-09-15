import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import App from './App';
import DocumentSearch from './pages/DocumentSearch';
import Login from './pages/Login';
import Register from './pages/Register';
import AdminUsers from './pages/AdminUsers';

function RequireAuth({ children }) {
  const token = localStorage.getItem('token');
  const location = useLocation();
  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return children;
}

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={
          <RequireAuth>
            <App />
          </RequireAuth>
        } />
        <Route path="/search" element={
          <RequireAuth>
            <DocumentSearch />
          </RequireAuth>
        } />
        <Route path="/admin/users" element={
          <RequireAuth>
            <AdminUsers />
          </RequireAuth>
        } />
      </Routes>
    </BrowserRouter>
  );
}
