import { Link, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, Shield } from 'lucide-react';

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/submit', label: 'Submit Dispute', icon: PlusCircle },
];

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 font-semibold text-white">
            <Shield className="w-5 h-5 text-blue-400" />
            <span>Visa Disputes</span>
          </Link>
          <nav className="flex gap-1 ml-6">
            {nav.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  pathname === to
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
