interface CardProps {
    title?: string;
    subtitle?: string;
    actions?: React.ReactNode;
    children: React.ReactNode;
    className?: string;
    noPadding?: boolean;
    style?: React.CSSProperties;
}

export default function Card({ title, subtitle, actions, children, className = "", noPadding, style }: CardProps) {
    return (
        <div className={`card ${className}`} style={style}>
            {title && (
                <div className="card__header">
                    <div>
                        <div className="card__title">{title}</div>
                        {subtitle && <div className="card__subtitle">{subtitle}</div>}
                    </div>
                    {actions && <div className="flex gap-2">{actions}</div>}
                </div>
            )}
            {noPadding ? children : <div className="card__body">{children}</div>}
        </div>
    );
}
