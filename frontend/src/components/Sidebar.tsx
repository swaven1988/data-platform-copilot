import { NavLink } from "react-router-dom";
import {
    LayoutDashboard,
    Database,
    Play,
    ShieldCheck,
    CreditCard,
    Activity,
    ScrollText,
    Zap,
} from "lucide-react";

const navItems = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/modeling", label: "Modeling", icon: Database },
    { to: "/execution", label: "Execution", icon: Play },
    { to: "/preflight", label: "Preflight", icon: ShieldCheck },
    { to: "/billing", label: "Billing", icon: CreditCard },
    { to: "/health", label: "Health", icon: Activity },
    { to: "/audit", label: "Audit Log", icon: ScrollText },
];

export default function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="sidebar__section-label">Navigation</div>
            {navItems.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                    key={to}
                    to={to}
                    end={end}
                    className={({ isActive }) =>
                        "sidebar__item" + (isActive ? " active" : "")
                    }
                >
                    <Icon size={15} strokeWidth={1.8} />
                    {label}
                </NavLink>
            ))}

            <div className="sidebar__footer">
                <div className="sidebar__section-label">System</div>
                <NavLink
                    to="/health"
                    className={({ isActive }) =>
                        "sidebar__item" + (isActive ? " active" : "")
                    }
                >
                    <Zap size={15} strokeWidth={1.8} />
                    System Status
                </NavLink>
            </div>
        </aside>
    );
}
