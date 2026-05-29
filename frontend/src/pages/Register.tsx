import { Navigate } from 'react-router-dom';

// Регистрация теперь часть единого флоу на /login (phone → code → register).
export function Register() {
  return <Navigate to="/login" replace />;
}
